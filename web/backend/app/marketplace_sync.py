"""Background marketplace synchronization into store-scoped snapshots."""
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from .db import SessionLocal
from .job_queue import enqueue, register_handler
from .marketplace_connections import decrypt_connection
from .models import MarketplaceAdvertisingLine, MarketplaceConnection, MarketplaceFinancialLine, MarketplaceSnapshot, Store
from .wb_analytics import fetch_wb_current_stocks, fetch_wb_sales_velocity
from .wb_content import fetch_wb_cards
from .wb_finance import fetch_financial_report_page
from .wb_feedbacks import fetch_wb_feedbacks
from .wb_promotion import date_chunks, fetch_advertising_stats, fetch_campaign_ids


def save_snapshot(db: Session, *, store_id: str, marketplace: str, snapshot_type: str, payload: dict) -> MarketplaceSnapshot:
    row = MarketplaceSnapshot(store_id=store_id, marketplace=marketplace, snapshot_type=snapshot_type, payload=payload, source_updated_at=datetime.now(timezone.utc))
    db.add(row); db.commit(); db.refresh(row); return row


def latest_snapshot(db: Session, *, store_id: str, marketplace: str, snapshot_type: str) -> MarketplaceSnapshot | None:
    return (db.query(MarketplaceSnapshot).filter(MarketplaceSnapshot.store_id==store_id, MarketplaceSnapshot.marketplace==marketplace, MarketplaceSnapshot.snapshot_type==snapshot_type).order_by(MarketplaceSnapshot.created_at.desc()).first())


@register_handler('marketplace.wb.feedbacks.sync')
async def sync_wb_feedbacks(payload: dict) -> None:
    store_id = str(payload.get('store_id') or '')
    if not store_id:
        raise ValueError('store_id is required')
    db = SessionLocal()
    try:
        connection = db.query(MarketplaceConnection).filter(MarketplaceConnection.store_id == store_id, MarketplaceConnection.marketplace == 'wildberries', MarketplaceConnection.enabled.is_(True)).first()
        if not connection:
            raise RuntimeError('Wildberries connection is not enabled for store')
        items, unanswered_count = await fetch_wb_feedbacks(decrypt_connection(connection))
        save_snapshot(db, store_id=store_id, marketplace='wildberries', snapshot_type='feedbacks', payload={'items': items, 'count': len(items), 'unanswered_count': unanswered_count, 'read_only': True, 'privacy_minimised': True})
    finally:
        db.close()


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


@register_handler('marketplace.wb.advertising.sync')
async def sync_wb_advertising(payload: dict) -> None:
    store_id=str(payload.get('store_id') or '')
    date_from=str(payload.get('date_from') or '')
    date_to=str(payload.get('date_to') or '')
    run_id=str(payload.get('run_id') or f'{date_from}:{date_to}')
    campaign_ids=[int(value) for value in (payload.get('campaign_ids') or []) if int(value)>0]
    date_index=max(0,int(payload.get('date_index') or 0))
    batch_index=max(0,int(payload.get('batch_index') or 0))
    if not store_id or not date_from or not date_to:
        raise ValueError('store_id, date_from and date_to are required')
    db=SessionLocal()
    try:
        connection=db.query(MarketplaceConnection).filter(
            MarketplaceConnection.store_id==store_id,
            MarketplaceConnection.marketplace=='wildberries',
            MarketplaceConnection.enabled.is_(True),
        ).first()
        if not connection: raise RuntimeError('Wildberries connection is not enabled for store')
        store=db.get(Store,store_id)
        if not store: raise RuntimeError('Store was not found')
        token=decrypt_connection(connection)
        if not campaign_ids:
            campaign_ids=await fetch_campaign_ids(token)
            if not campaign_ids:
                save_snapshot(db,store_id=store_id,marketplace='wildberries',snapshot_type='advertising_sync',payload={'date_from':date_from,'date_to':date_to,'run_id':run_id,'complete':True,'campaign_count':0,'page_number':0,'page_rows':0})
                return
        intervals=date_chunks(date_from,date_to)
        batches=[campaign_ids[index:index+50] for index in range(0,len(campaign_ids),50)]
        if date_index>=len(intervals) or batch_index>=len(batches):
            raise ValueError('advertising cursor is outside the requested range')
        begin,end=intervals[date_index]
        rows=await fetch_advertising_stats(token,ids=batches[batch_index],date_from=begin,date_to=end)
        inserted=0; updated=0
        existing_rows=db.query(MarketplaceAdvertisingLine).filter(
            MarketplaceAdvertisingLine.store_id==store_id,
            MarketplaceAdvertisingLine.marketplace=='wildberries',
            MarketplaceAdvertisingLine.campaign_id.in_(batches[batch_index]),
            MarketplaceAdvertisingLine.event_date>=begin,
            MarketplaceAdvertisingLine.event_date<=end,
        ).all()
        existing_by_source={row.source_line_id:row for row in existing_rows}
        seen=set()
        for item in rows:
            seen.add(item['source_line_id'])
            row=existing_by_source.get(item['source_line_id'])
            if row is None:
                db.add(MarketplaceAdvertisingLine(store_id=store_id,marketplace='wildberries',**item)); inserted+=1
            elif row.source_sha256!=item['source_sha256']:
                for key,value in item.items(): setattr(row,key,value)
                updated+=1
        deleted=0
        for stale in existing_rows:
            if stale.source_line_id not in seen: db.delete(stale); deleted+=1
        db.commit()
        next_date_index=date_index
        next_batch_index=batch_index+1
        if next_batch_index>=len(batches): next_date_index+=1; next_batch_index=0
        complete=next_date_index>=len(intervals)
        page_number=date_index*len(batches)+batch_index+1
        save_snapshot(db,store_id=store_id,marketplace='wildberries',snapshot_type='advertising_sync',payload={
            'date_from':date_from,'date_to':date_to,'run_id':run_id,'complete':complete,
            'campaign_count':len(campaign_ids),'date_chunks':len(intervals),'campaign_batches':len(batches),
            'page_number':page_number,'page_rows':len(rows),'inserted_rows':inserted,'updated_rows':updated,'deleted_rows':deleted,
            'date_index':date_index,'batch_index':batch_index,
        })
        if not complete:
            enqueue(db,job_type='marketplace.wb.advertising.sync',idempotency_key=f'wb-ads:{store_id}:{run_id}:{next_date_index}:{next_batch_index}',payload={
                'store_id':store_id,'date_from':date_from,'date_to':date_to,'run_id':run_id,
                'campaign_ids':campaign_ids,'date_index':next_date_index,'batch_index':next_batch_index,
            },workspace_id=store.workspace_id,store_id=store_id,priority=46,max_attempts=5,available_at=datetime.now(timezone.utc)+timedelta(seconds=21))
    finally:
        db.close()
