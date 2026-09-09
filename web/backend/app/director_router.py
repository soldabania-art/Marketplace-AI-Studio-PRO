from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .db import get_db
from .director_service import build_director
from .marketplace_sync import latest_snapshot
from .models import User
from .profit_center_router import profit_center
from .security import get_current_user
from .seller_data_router import _connection
from .store_access import resolve_store
from .wb_analytics import build_network_supply_inputs

router = APIRouter(prefix='/director', tags=['director'])


def _source(snapshot, name: str, *, complete: bool | None = None, coverage_matches: bool = True) -> dict:
    if snapshot is None: state, age = 'missing', None
    else:
        created = snapshot.created_at
        if created.tzinfo is None: created = created.replace(tzinfo=timezone.utc)
        age = max(0, int((datetime.now(timezone.utc) - created).total_seconds()))
        state = 'incomplete' if complete is False or not coverage_matches else ('stale' if age > 900 else 'live')
    return {'name': name, 'state': state, 'last_snapshot_at': snapshot.created_at if snapshot else None, 'age_seconds': age}


@router.get('')
def daily_director(store_id: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    store = resolve_store(db, user, store_id); _connection(db, store.id)
    snapshot = lambda name: latest_snapshot(db, store_id=store.id, marketplace='wildberries', snapshot_type=name)
    catalog, stocks, sales = snapshot('catalog'), snapshot('stocks'), snapshot('sales_velocity_7d')
    finance, advertising = snapshot('finance_realization_sync'), snapshot('advertising_sync')
    end = date.today(); date_from, date_to = (end - timedelta(days=29)).isoformat(), end.isoformat()
    finance_payload = dict(finance.payload or {}) if finance else {}
    advertising_payload = dict(advertising.payload or {}) if advertising else {}
    sources = [
        _source(catalog, 'catalog'), _source(stocks, 'stocks'), _source(sales, 'sales_velocity_7d'),
        _source(finance, 'finance_realization_sync', complete=bool(finance_payload.get('complete')) if finance else None,
                coverage_matches=finance_payload.get('date_from') == date_from and finance_payload.get('date_to') == date_to),
        _source(advertising, 'advertising_sync', complete=bool(advertising_payload.get('complete')) if advertising else None,
                coverage_matches=advertising_payload.get('date_from') == date_from and advertising_payload.get('date_to') == date_to),
    ]
    catalog_items = list((catalog.payload or {}).get('items') or []) if catalog else []
    stock_rows = list((stocks.payload or {}).get('rows') or []) if stocks else []
    sales_rows = list((sales.payload or {}).get('items') or []) if sales else []
    sales_map = {int(row['nm_id']): row for row in sales_rows if row.get('nm_id') is not None}
    supply_facts = build_network_supply_inputs(stock_rows, sales_map) if stocks and sales else []
    profit = profit_center(store_id=store.id, period_days=30, user=user, db=db)
    return build_director(store_id=store.id, store_name=store.name, sources=sources,
                          catalog_items=catalog_items, supply_facts=supply_facts, profit=profit)
