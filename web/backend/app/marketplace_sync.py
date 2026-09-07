"""Background marketplace synchronization into store-scoped snapshots."""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from .db import SessionLocal
from .job_queue import register_handler
from .marketplace_connections import decrypt_connection
from .models import MarketplaceConnection, MarketplaceSnapshot
from .wb_analytics import fetch_wb_current_stocks, fetch_wb_sales_velocity
from .wb_content import fetch_wb_cards


def save_snapshot(db: Session, *, store_id: str, marketplace: str, snapshot_type: str, payload: dict) -> MarketplaceSnapshot:
    row = MarketplaceSnapshot(store_id=store_id, marketplace=marketplace, snapshot_type=snapshot_type, payload=payload, source_updated_at=datetime.now(timezone.utc))
    db.add(row); db.commit(); db.refresh(row); return row


def latest_snapshot(db: Session, *, store_id: str, marketplace: str, snapshot_type: str) -> MarketplaceSnapshot | None:
    return (db.query(MarketplaceSnapshot).filter(MarketplaceSnapshot.store_id==store_id, MarketplaceSnapshot.marketplace==marketplace, MarketplaceSnapshot.snapshot_type==snapshot_type).order_by(MarketplaceSnapshot.created_at.desc()).first())


@register_handler('marketplace.wb.analytics.sync')
async def sync_wb_analytics(payload: dict) -> None:
    store_id = str(payload.get('store_id') or '')
    if not store_id:
        raise ValueError('store_id is required')
    db = SessionLocal()
    try:
        connection = db.query(MarketplaceConnection).filter(MarketplaceConnection.store_id==store_id, MarketplaceConnection.marketplace=='wildberries', MarketplaceConnection.enabled.is_(True)).first()
        if not connection:
            raise RuntimeError('Wildberries connection is not enabled for store')
        token = decrypt_connection(connection)
        cards = await fetch_wb_cards(token)
        stocks = await fetch_wb_current_stocks(token)
        sales = await fetch_wb_sales_velocity(token, period_days=7)
        save_snapshot(db, store_id=store_id, marketplace='wildberries', snapshot_type='catalog', payload={'items': cards, 'count': len(cards)})
        save_snapshot(db, store_id=store_id, marketplace='wildberries', snapshot_type='stocks', payload={'rows': stocks, 'count': len(stocks)})
        save_snapshot(db, store_id=store_id, marketplace='wildberries', snapshot_type='sales_velocity_7d', payload={'items': list(sales.values()), 'count': len(sales)})
    finally:
        db.close()
