import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .db import get_db
from .fbo_service import fetch_wb_slots
from .marketplace_connections import decrypt_connection
from .models import MarketplaceConnection, User
from .security import get_current_user
from .smart_fbo import SupplyInput, recommend_many
from .store_access import resolve_store
from .wb_analytics import build_network_supply_inputs, fetch_wb_current_stocks, fetch_wb_sales_velocity

router = APIRouter(prefix='/smart-fbo', tags=['smart-fbo'])

class SupplyRow(BaseModel):
    sku: str = Field(min_length=1, max_length=160)
    warehouse_id: int | None = None
    warehouse_name: str = Field(min_length=1, max_length=200)
    stock: int = Field(ge=0, le=10_000_000)
    avg_daily_sales: float = Field(ge=0, le=1_000_000)
    lead_time_days: int = Field(default=7, ge=0, le=90)
    target_cover_days: int = Field(default=21, ge=1, le=180)
    safety_days: int = Field(default=5, ge=0, le=90)
    acceptance_coefficient: int | None = None

class PlanRequest(BaseModel):
    store_id: str | None = None
    rows: list[SupplyRow] = Field(min_length=1, max_length=5000)

@router.post('/plan')
def create_plan(payload: PlanRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    store = resolve_store(db, current_user, payload.store_id)
    items = [SupplyInput(**row.model_dump()) for row in payload.rows]
    recommendations = recommend_many(items)
    critical = sum(1 for row in recommendations if row['urgency'] == 'critical')
    available = sum(1 for row in recommendations if row['recommended_qty'] > 0 and row['acceptance_available'])
    return {
        'store_id': store.id,
        'store_name': store.name,
        'mode': 'deterministic',
        'live_marketplace_data': False,
        'source': 'request_facts',
        'summary': {
            'sku_warehouse_pairs': len(recommendations),
            'critical': critical,
            'ready_to_supply': available,
            'recommended_units': sum(row['recommended_qty'] for row in recommendations),
        },
        'recommendations': recommendations,
        'notice': 'Расчёт выполнен по переданным фактам.',
    }


def _wb_connection(db: Session, store_id: str) -> MarketplaceConnection:
    connection = db.query(MarketplaceConnection).filter(
        MarketplaceConnection.store_id == store_id,
        MarketplaceConnection.marketplace == 'wildberries',
        MarketplaceConnection.enabled.is_(True),
    ).first()
    if not connection:
        raise HTTPException(status_code=409, detail='Сначала подключите Wildberries для выбранного магазина.')
    return connection


def _map_wb_error(exc: httpx.HTTPStatusError) -> HTTPException:
    status = exc.response.status_code if exc.response is not None else 502
    if status in {401, 403}:
        return HTTPException(status_code=409, detail='Для Smart FBO нужен действующий WB-токен с доступом к Аналитике. Проверьте права подключения.')
    if status == 402:
        return HTTPException(status_code=409, detail='Wildberries ограничил доступ к требуемой аналитике для этого аккаунта/тарифа.')
    if status == 429:
        return HTTPException(status_code=429, detail='Лимит WB Analytics временно исчерпан. Задание следует повторить через очередь.')
    return HTTPException(status_code=502, detail='Wildberries Analytics временно недоступен.')


@router.get('/live')
async def live_plan(
    store_id: str | None = None,
    period_days: int = Query(default=7, ge=1, le=7),
    lead_time_days: int = Query(default=7, ge=0, le=90),
    target_cover_days: int = Query(default=21, ge=1, le=180),
    safety_days: int = Query(default=5, ge=0, le=90),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Build a truthful live WB supply plan from official stock + funnel data.

    v1 deliberately calculates quantity at the WB-network/SKU level. It does not
    invent warehouse demand allocation. Available acceptance slots are returned
    as candidates; regional/warehouse demand allocation is the next layer.
    """
    store = resolve_store(db, current_user, store_id)
    token = decrypt_connection(_wb_connection(db, store.id))
    try:
        stocks = await fetch_wb_current_stocks(token)
        sales = await fetch_wb_sales_velocity(token, period_days=period_days)
        slots = await fetch_wb_slots(token)
    except httpx.HTTPStatusError as exc:
        raise _map_wb_error(exc)
    except httpx.RequestError:
        raise HTTPException(status_code=502, detail='Не удалось связаться с Wildberries.')

    facts = build_network_supply_inputs(stocks, sales)
    supply_inputs = [SupplyInput(
        sku=row['sku'],
        warehouse_id=None,
        warehouse_name='Сеть складов WB',
        stock=row['stock'],
        avg_daily_sales=row['avg_daily_sales'],
        lead_time_days=lead_time_days,
        target_cover_days=target_cover_days,
        safety_days=safety_days,
        acceptance_coefficient=None,
    ) for row in facts]
    recommendations = recommend_many(supply_inputs)
    facts_by_sku = {row['sku']: row for row in facts}
    for row in recommendations:
        fact = facts_by_sku.get(row['sku'], {})
        row['nm_id'] = fact.get('nm_id')
        row['title'] = fact.get('title', '')
        row['orders_period'] = fact.get('orders_period', 0)
        row['sales_period_days'] = fact.get('period_days', period_days)
        row['warehouse_stocks'] = fact.get('warehouse_stocks', [])
        row['warehouse_allocation_status'] = 'pending_regional_demand'

    candidate_slots = slots[:200]
    return {
        'store_id': store.id,
        'store_name': store.name,
        'marketplace': 'wildberries',
        'mode': 'deterministic_live_v1',
        'live_marketplace_data': True,
        'sources': {
            'stock': 'WB Analytics: current WB warehouse inventory',
            'sales_velocity': f'WB Sales Funnel: last {period_days} days orders',
            'acceptance': 'WB acceptance coefficients',
        },
        'summary': {
            'products_with_sales_history': len(sales),
            'stock_rows': len(stocks),
            'critical': sum(1 for row in recommendations if row['urgency'] == 'critical'),
            'recommended_units': sum(row['recommended_qty'] for row in recommendations),
            'candidate_acceptance_slots': len(slots),
        },
        'recommendations': recommendations,
        'candidate_acceptance_slots': candidate_slots,
        'notice': 'Количество рассчитано по реальным остаткам и заказам WB. Распределение количества между конкретными складами пока не вычисляется без проверенной складской/региональной скорости спроса.',
    }
