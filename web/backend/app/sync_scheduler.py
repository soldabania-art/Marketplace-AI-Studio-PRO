import asyncio
import hashlib
import logging
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from .config import get_settings
from .data_health import store_data_health
from .data_health_incidents import reconcile_health_incidents
from .db import SessionLocal
from .job_queue import enqueue
from .models import BackgroundJob, MarketplaceConnection, Store
from sqlalchemy import text

logger = logging.getLogger(__name__)


@contextmanager
def _store_lease(db, store_id: str):
    if db.get_bind().dialect.name != 'postgresql':
        yield True
        return
    raw = int.from_bytes(hashlib.blake2b(f'sync:wildberries:{store_id}'.encode(), digest_size=8).digest(), 'big')
    key = raw if raw < 2**63 else raw - 2**64
    acquired = bool(db.execute(text('SELECT pg_try_advisory_lock(:key)'), {'key': key}).scalar())
    try:
        yield acquired
    finally:
        if acquired:
            db.execute(text('SELECT pg_advisory_unlock(:key)'), {'key': key})


def _bucket(now: datetime, seconds: int) -> int:
    return int(now.timestamp() // max(60, seconds))


def _due(source: dict, interval_seconds: int) -> bool:
    if source['status'] in {'missing', 'stale', 'error'}:
        return True
    return source['status'] == 'delayed' and int(source.get('age_seconds') or 0) >= interval_seconds


def _was_missing(db, key: str) -> bool:
    return db.query(BackgroundJob.id).filter(BackgroundJob.idempotency_key == key).first() is None


def schedule_due_syncs_once(now: datetime | None = None) -> dict[str, int]:
    """Schedule read-only marketplace jobs; unique keys make concurrent workers safe."""
    settings = get_settings(); now = now or datetime.now(timezone.utc)
    totals = {'stores': 0, 'analytics': 0, 'finance': 0, 'advertising': 0, 'incidents_opened': 0, 'incidents_resolved': 0}
    db = SessionLocal()
    try:
        rows = db.query(MarketplaceConnection, Store).join(Store, Store.id == MarketplaceConnection.store_id).filter(
            MarketplaceConnection.marketplace == 'wildberries',
            MarketplaceConnection.enabled.is_(True),
            Store.is_active.is_(True),
        ).all()
        for _, store in rows:
            with _store_lease(db, store.id) as acquired:
                if not acquired:
                    continue
                totals['stores'] += 1
                health = store_data_health(db, store.id, now=now)
                incident_stats = reconcile_health_incidents(db, workspace_id=store.workspace_id, store_id=store.id, sources=health['sources'], now=now)
                totals['incidents_opened'] += incident_stats['opened']; totals['incidents_resolved'] += incident_stats['resolved']
                sources = {item['key']: item for item in health['sources']}
                if any(_due(sources[key], settings.sync_analytics_interval_seconds) for key in ('catalog', 'stocks', 'sales')):
                    key = f"auto-wb-analytics:{store.id}:{_bucket(now, settings.sync_analytics_interval_seconds)}"
                    is_new = _was_missing(db, key)
                    enqueue(db, job_type='marketplace.wb.analytics.sync', idempotency_key=key,
                        payload={'store_id': store.id, 'origin': 'scheduler'}, workspace_id=store.workspace_id,
                        store_id=store.id, priority=65, max_attempts=5)
                    totals['analytics'] += int(is_new)
                period_to = now.date(); period_from = period_to - timedelta(days=29)
                common = {'store_id': store.id, 'date_from': period_from.isoformat(), 'date_to': period_to.isoformat(), 'run_id': f'auto:{period_from}:{period_to}', 'origin': 'scheduler'}
                if _due(sources['finance'], settings.sync_finance_interval_seconds):
                    suffix = f"recovery:{_bucket(now, settings.sync_dead_retry_interval_seconds)}" if sources['finance']['status'] == 'error' else str(period_to)
                    key = f'auto-wb-finance:{store.id}:{suffix}'; is_new = _was_missing(db, key)
                    enqueue(db, job_type='marketplace.wb.finance.sync', idempotency_key=key,
                        payload=common | {'rrd_id': 0, 'page_number': 1}, workspace_id=store.workspace_id, store_id=store.id, priority=70, max_attempts=5)
                    totals['finance'] += int(is_new)
                if _due(sources['advertising'], settings.sync_advertising_interval_seconds):
                    suffix = f"recovery:{_bucket(now, settings.sync_dead_retry_interval_seconds)}" if sources['advertising']['status'] == 'error' else str(period_to)
                    key = f'auto-wb-advertising:{store.id}:{suffix}'; is_new = _was_missing(db, key)
                    enqueue(db, job_type='marketplace.wb.advertising.sync', idempotency_key=key,
                        payload=common | {'campaign_ids': [], 'date_index': 0, 'batch_index': 0}, workspace_id=store.workspace_id, store_id=store.id, priority=71, max_attempts=5)
                    totals['advertising'] += int(is_new)
        return totals
    finally:
        db.close()


async def sync_scheduler_forever(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            logger.info('Automatic sync scheduler stats=%s', schedule_due_syncs_once())
        except Exception as exc:
            logger.error('Automatic sync scheduler cycle failed error_type=%s', type(exc).__name__)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=max(30, get_settings().sync_scheduler_seconds))
        except asyncio.TimeoutError:
            pass
