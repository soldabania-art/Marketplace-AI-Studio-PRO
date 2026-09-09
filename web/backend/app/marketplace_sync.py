"""Background marketplace synchronization into store-scoped snapshots."""
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from .db import SessionLocal
from .job_queue import enqueue, register_handler
from .marketplace_connections import decrypt_connection
from .models import MarketplaceConnection, MarketplaceFinancialLine, MarketplaceSnapshot, Store
from .wb_analytics import fetch_wb_current_stocks, fetch_wb_sales_velocity
from .wb_content import fetch_wb_cards
from .wb_finance import fetch_financial_report_page


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


@register_handler('marketplace.wb.finance.sync')
async def sync_wb_finance(payload: dict) -> None:
    store_id = str(payload.get('store_id') or '')
    date_from = str(payload.get('date_from') or '')
    date_to = str(payload.get('date_to') or '')
    rrd_id = int(payload.get('rrd_id') or 0)
    page_number = max(1, int(payload.get('page_number') or 1))
    run_id = str(payload.get('run_id') or f'{date_from}:{date_to}')
    if not store_id or not date_from or not date_to:
        raise ValueError('store_id, date_from and date_to are required')
    db = SessionLocal()
    try:
        connection = db.query(MarketplaceConnection).filter(
            MarketplaceConnection.store_id == store_id,
            MarketplaceConnection.marketplace == 'wildberries',
            MarketplaceConnection.enabled.is_(True),
        ).first()
        if not connection:
            raise RuntimeError('Wildberries connection is not enabled for store')
        store = db.get(Store, store_id)
        if not store:
            raise RuntimeError('Store was not found')
        token = decrypt_connection(connection)
        rows = await fetch_financial_report_page(token, date_from=date_from, date_to=date_to, rrd_id=rrd_id)
        inserted = 0
        updated = 0
        for item in rows:
            row = db.query(MarketplaceFinancialLine).filter(
                MarketplaceFinancialLine.store_id == store_id,
                MarketplaceFinancialLine.marketplace == 'wildberries',
                MarketplaceFinancialLine.source_line_id == item['source_line_id'],
            ).first()
            if row is None:
                row = MarketplaceFinancialLine(store_id=store_id, marketplace='wildberries', **item)
                db.add(row)
                inserted += 1
            elif row.source_sha256 != item['source_sha256']:
                for key, value in item.items():
                    setattr(row, key, value)
                updated += 1
        db.commit()
        complete = not rows
        next_rrd_id = rrd_id
        if rows:
            next_rrd_id = int(rows[-1]['source_line_id'])
            if next_rrd_id <= rrd_id:
                raise RuntimeError('Wildberries returned a non-advancing finance cursor')
        save_snapshot(
            db,
            store_id=store_id,
            marketplace='wildberries',
            snapshot_type='finance_realization_sync',
            payload={
                'date_from': date_from,
                'date_to': date_to,
                'run_id': run_id,
                'complete': complete,
                'page_number': page_number,
                'page_rows': len(rows),
                'inserted_rows': inserted,
                'updated_rows': updated,
                'rrd_id': next_rrd_id,
            },
        )
        if rows:
            enqueue(
                db,
                job_type='marketplace.wb.finance.sync',
                idempotency_key=f'wb-finance:{store_id}:{run_id}:{next_rrd_id}',
                payload={'store_id': store_id, 'date_from': date_from, 'date_to': date_to, 'rrd_id': next_rrd_id, 'page_number': page_number + 1, 'run_id': run_id},
                workspace_id=store.workspace_id,
                store_id=store_id,
                priority=45,
                max_attempts=5,
                available_at=datetime.now(timezone.utc) + timedelta(seconds=61),
            )
    finally:
        db.close()
