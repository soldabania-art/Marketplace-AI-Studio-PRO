from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .db import get_db
from .job_queue import enqueue
from .marketplace_sync import latest_snapshot
from .models import MarketplaceConnection, MarketplaceFinancialLine, ProductCostProfile, User
from .security import get_current_user
from .store_access import require_store_admin, resolve_store

router = APIRouter(prefix='/profit-center', tags=['profit-center'])


class ProfitSyncRequest(BaseModel):
    store_id: str = Field(min_length=1, max_length=36)
    period_days: int = Field(default=30, ge=7, le=90)


class ProductCostRequest(BaseModel):
    store_id: str = Field(min_length=1, max_length=36)
    cogs_rub: Decimal = Field(ge=Decimal('0.01'), le=Decimal('100000000'))
    confirmed: bool


def _connection(db: Session, store_id: str):
    row = db.query(MarketplaceConnection).filter(
        MarketplaceConnection.store_id == store_id,
        MarketplaceConnection.marketplace == 'wildberries',
        MarketplaceConnection.enabled.is_(True),
    ).first()
    if not row:
        raise HTTPException(409, 'Wildberries не подключён к выбранному магазину.')
    return row


def _period(period_days: int) -> tuple[str, str]:
    end = date.today()
    start = end - timedelta(days=max(7, min(90, period_days)) - 1)
    return start.isoformat(), end.isoformat()


def _rubles(kopecks: int) -> str:
    return f'{Decimal(kopecks) / Decimal(100):.2f}'


def _line_in_period(row: MarketplaceFinancialLine, date_from: str, date_to: str) -> bool:
    value = str(row.event_date or '')[:10]
    return bool(value and date_from <= value <= date_to)


def _totals(rows: list[MarketplaceFinancialLine]) -> dict:
    keys = (
        'gross_kopecks', 'payout_kopecks', 'commission_kopecks', 'logistics_kopecks',
        'acquiring_kopecks', 'storage_kopecks', 'acceptance_kopecks',
        'penalty_kopecks', 'deduction_kopecks', 'additional_payment_kopecks',
    )
    result = {key: sum(int(getattr(row, key) or 0) for row in rows) for key in keys}
    result['net_units'] = sum(int(row.quantity or 0) for row in rows)
    result['wb_net_kopecks'] = (
        result['payout_kopecks']
        - result['logistics_kopecks']
        - result['acquiring_kopecks']
        - result['storage_kopecks']
        - result['acceptance_kopecks']
        - result['penalty_kopecks']
        - result['deduction_kopecks']
        + result['additional_payment_kopecks']
    )
    return result


def _public_amounts(totals: dict) -> dict:
    return {key.removesuffix('_kopecks'): _rubles(value) if key.endswith('_kopecks') else value for key, value in totals.items()}


@router.post('/sync', status_code=202)
def start_profit_sync(payload: ProfitSyncRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    store = resolve_store(db, user, payload.store_id)
    _connection(db, store.id)
    date_from, date_to = _period(payload.period_days)
    run_id = f'{date_from}:{date_to}:{datetime.now(timezone.utc).strftime("%Y%m%d%H")}'
    job = enqueue(
        db,
        job_type='marketplace.wb.finance.sync',
        idempotency_key=f'wb-finance:{store.id}:{run_id}:start',
        payload={'store_id': store.id, 'date_from': date_from, 'date_to': date_to, 'rrd_id': 0, 'page_number': 1, 'run_id': run_id},
        workspace_id=store.workspace_id,
        store_id=store.id,
        priority=45,
        max_attempts=5,
    )
    return {'job_id': job.id, 'status': job.status.value, 'date_from': date_from, 'date_to': date_to, 'message': 'Финансовый отчёт поставлен в безопасную фоновую очередь.'}


@router.patch('/costs/{nm_id}')
def save_product_cost(nm_id: int, payload: ProductCostRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if nm_id <= 0:
        raise HTTPException(422, 'Некорректный nmId.')
    if not payload.confirmed:
        raise HTTPException(422, 'Подтвердите, что себестоимость взята из ваших документов.')
    store = resolve_store(db, user, payload.store_id)
    require_store_admin(db, user, store)
    _connection(db, store.id)
    try:
        kopecks = int((payload.cogs_rub * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    except InvalidOperation as exc:
        raise HTTPException(422, 'Некорректная себестоимость.') from exc
    row = db.query(ProductCostProfile).filter(
        ProductCostProfile.store_id == store.id,
        ProductCostProfile.marketplace == 'wildberries',
        ProductCostProfile.nm_id == nm_id,
    ).first()
    now = datetime.now(timezone.utc)
    if row is None:
        row = ProductCostProfile(store_id=store.id, marketplace='wildberries', nm_id=nm_id, cogs_kopecks=kopecks, confirmed_by_user_id=user.id, source='manual', confirmed_at=now)
        db.add(row)
    else:
        row.cogs_kopecks = kopecks
        row.confirmed_by_user_id = user.id
        row.source = 'manual'
        row.confirmed_at = now
    db.commit()
    db.refresh(row)
    return {'nm_id': row.nm_id, 'cogs_rub': _rubles(row.cogs_kopecks), 'source': row.source, 'confirmed_at': row.confirmed_at}


@router.get('')
def profit_center(store_id: str, period_days: int = 30, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    store = resolve_store(db, user, store_id)
    _connection(db, store.id)
    days = max(7, min(90, int(period_days)))
    date_from, date_to = _period(days)
    sync = latest_snapshot(db, store_id=store.id, marketplace='wildberries', snapshot_type='finance_realization_sync')
    sync_payload = dict(sync.payload or {}) if sync else {}
    coverage_matches = sync_payload.get('date_from') == date_from and sync_payload.get('date_to') == date_to
    all_lines = db.query(MarketplaceFinancialLine).filter(
        MarketplaceFinancialLine.store_id == store.id,
        MarketplaceFinancialLine.marketplace == 'wildberries',
    ).all()
    lines = [row for row in all_lines if _line_in_period(row, date_from, date_to)]
    costs = db.query(ProductCostProfile).filter(
        ProductCostProfile.store_id == store.id,
        ProductCostProfile.marketplace == 'wildberries',
    ).all()
    cost_by_nm = {row.nm_id: row for row in costs}
    catalog = latest_snapshot(db, store_id=store.id, marketplace='wildberries', snapshot_type='catalog')
    cards = {(item.get('nm_id')): item for item in ((catalog.payload or {}).get('items') or [])} if catalog else {}
    by_nm: dict[int, list[MarketplaceFinancialLine]] = {}
    unallocated = []
    for row in lines:
        if row.nm_id:
            by_nm.setdefault(int(row.nm_id), []).append(row)
        else:
            unallocated.append(row)
    products = []
    confirmed_products = 0
    for nm_id, product_lines in by_nm.items():
        values = _totals(product_lines)
        cost = cost_by_nm.get(nm_id)
        net_units = max(0, int(values['net_units']))
        cogs_total = int(cost.cogs_kopecks) * net_units if cost else None
        contribution = values['wb_net_kopecks'] - cogs_total if cogs_total is not None else None
        if cost:
            confirmed_products += 1
        card = cards.get(nm_id) or {}
        products.append({
            'nm_id': nm_id,
            'vendor_code': card.get('vendor_code') or product_lines[0].vendor_code,
            'title': card.get('title') or product_lines[0].title or f'WB товар {nm_id}',
            'amounts': _public_amounts(values),
            'cogs_per_unit': _rubles(cost.cogs_kopecks) if cost else None,
            'cogs_total': _rubles(cogs_total) if cogs_total is not None else None,
            'contribution_before_tax_ads': _rubles(contribution) if contribution is not None else None,
            'cost_confirmed_at': cost.confirmed_at if cost else None,
        })
    products.sort(key=lambda item: (item['contribution_before_tax_ads'] is None, Decimal(item['contribution_before_tax_ads'] or '0'), item['nm_id']))
    totals = _totals(lines)
    total_cogs = sum(int(cost_by_nm[nm_id].cogs_kopecks) * max(0, _totals(rows)['net_units']) for nm_id, rows in by_nm.items() if nm_id in cost_by_nm)
    all_costs_known = bool(by_nm) and confirmed_products == len(by_nm)
    contribution = totals['wb_net_kopecks'] - total_cogs if all_costs_known else None
    return {
        'store_id': store.id,
        'store_name': store.name,
        'marketplace': 'wildberries',
        'period': {'days': days, 'date_from': date_from, 'date_to': date_to},
        'sync': {
            'started': bool(sync),
            'coverage_matches': coverage_matches,
            'complete': bool(coverage_matches and sync_payload.get('complete')),
            'page_number': sync_payload.get('page_number'),
            'last_snapshot_at': sync.created_at if sync else None,
            'next_rrd_id': sync_payload.get('rrd_id'),
        },
        'source_line_count': len(lines),
        'amounts': _public_amounts(totals),
        'cogs_total': _rubles(total_cogs) if all_costs_known else None,
        'contribution_before_tax_ads': _rubles(contribution) if contribution is not None else None,
        'profit_status': 'partial',
        'final_profit': None,
        'completeness': {
            'wb_finance': bool(coverage_matches and sync_payload.get('complete')),
            'cogs': all_costs_known,
            'advertising': False,
            'tax': False,
            'unallocated_financial_lines': len(unallocated),
        },
        'formula': 'WB к перечислению − логистика − эквайринг − хранение − приёмка − штрафы − удержания + доплаты − подтверждённая себестоимость',
        'warning': 'Это вклад до налогов и рекламы, а не окончательная чистая прибыль.',
        'products': products,
    }
