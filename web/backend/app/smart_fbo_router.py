from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .db import get_db
from .models import User
from .security import get_current_user
from .smart_fbo import SupplyInput, recommend_many
from .store_access import resolve_store

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
        'notice': 'Расчёт выполнен по переданным фактам. Автоматическая загрузка продаж и остатков WB подключается отдельно.',
    }
