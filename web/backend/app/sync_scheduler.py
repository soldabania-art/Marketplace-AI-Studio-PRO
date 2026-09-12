import asyncio
import hashlib
import logging
from contextlib import contextmanager
from datetime import datetime, timezone

from .config import get_settings
from .data_health import expected_coverage, refresh_due, store_data_health
from .data_health_incidents import reconcile_health_incidents
from .db import SessionLocal
from .job_queue import enqueue
from .models import BackgroundJob, JobStatus, MarketplaceConnection, Store
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


def _was_missing(db, key: str) -> bool:
    return db.query(BackgroundJob.id).filter(BackgroundJob.idempotency_key == key).first() is None


def _sync_job_lock_key(store_id: str, job_type: str) -> int:
    raw = int.from_bytes(hashlib.blake2b(f'job:{store_id}:{job_type}'.encode(), digest_size=8).digest(), 'big')
    return raw if raw < 2**63 else raw - 2**64


def enqueue_sync_job(
    db,
    *,
    store,
    group: str,
    payload: dict,
    now: datetime | None = None,
    suffix: str | None = None,
    priority: int,
) -> tuple[BackgroundJob, bool]:
    """Deduplicate a root sync across scheduler, Director and browser endpoints."""
    settings = get_settings()
    specs = {
        'analytics': ('marketplace.wb.analytics.sync', settings.sync_analytics_interval_seconds),
        'feedbacks': ('marketplace.wb.feedbacks.sync', settings.sync_feedbacks_interval_seconds),
        'finance': ('marketplace.wb.finance.sync', settings.sync_finance_interval_seconds),
        'advertising': ('marketplace.wb.advertising.sync', settings.sync_advertising_interval_seconds),
    }
    if group not in specs:
        raise ValueError(f'Unsupported sync group: {group}')
    job_type, interval = specs[group]
    if db.get_bind().dialect.name == 'postgresql':
        db.execute(text('SELECT pg_advisory_xact_lock(:key)'), {'key': _sync_job_lock_key(store.id, job_type)})
    active = db.query(BackgroundJob).filter(
        BackgroundJob.store_id == store.id,
        BackgroundJob.job_type == job_type,
        BackgroundJob.status.in_([JobStatus.queued, JobStatus.running, JobStatus.retry]),
    ).order_by(BackgroundJob.created_at.desc()).first()
    if active:
        return active, False
    current = now or datetime.now(timezone.utc)
    namespace = suffix or str(_bucket(current, interval))
    key = f'wb-sync:{group}:{store.id}:{namespace}'
    is_new = _was_missing(db, key)
    job = enqueue(
        db,
        job_type=job_type,
        idempotency_key=key,
        payload=payload,
        workspace_id=store.workspace_id,
        store_id=store.id,
        priority=priority,
        max_attempts=5,
    )
    return job, is_new


def schedule_due_syncs_once(now: datetime | None = None) -> dict[str, int]:
    """Schedule read-only marketplace jobs; unique keys make concurrent workers safe."""
    settings = get_settings(); now = now or datetime.now(timezone.utc)
    totals = {'stores': 0, 'analytics': 0, 'finance': 0, 'advertising': 0, 'feedbacks': 0, 'incidents_opened': 0, 'incidents_resolved': 0}
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
                if any(refresh_due(sources[key], settings.sync_analytics_interval_seconds) for key in ('catalog', 'stocks', 'sales')):
                    _, is_new = enqueue_sync_job(db, store=store, group='analytics', now=now,
                        payload={'store_id': store.id, 'origin': 'scheduler'}, priority=65)
                    totals['analytics'] += int(is_new)
                coverage = expected_coverage('finance', now=now, period_days=30)
                period_from, period_to = coverage['date_from'], coverage['date_to']
                if refresh_due(sources['finance'], settings.sync_finance_interval_seconds):
                    suffix = f"recovery:{_bucket(now, settings.sync_dead_retry_interval_seconds)}" if sources['finance']['status'] == 'error' else f'period:{period_to}'
                    run_id = f'auto:finance:{period_from}:{period_to}:{suffix}'
                    _, is_new = enqueue_sync_job(db, store=store, group='finance', now=now,
                        suffix=f'{run_id}:start',
                        payload={'store_id': store.id, 'date_from': period_from, 'date_to': period_to,
                                 'run_id': run_id, 'origin': 'scheduler', 'rrd_id': 0, 'page_number': 1},
                        priority=70)
                    totals['finance'] += int(is_new)
                if refresh_due(sources['advertising'], settings.sync_advertising_interval_seconds):
                    suffix = f"recovery:{_bucket(now, settings.sync_dead_retry_interval_seconds)}" if sources['advertising']['status'] == 'error' else f'period:{period_to}'
                    run_id = f'auto:advertising:{period_from}:{period_to}:{suffix}'
                    _, is_new = enqueue_sync_job(db, store=store, group='advertising', now=now,
                        suffix=f'{run_id}:start',
                        payload={'store_id': store.id, 'date_from': period_from, 'date_to': period_to,
                                 'run_id': run_id, 'origin': 'scheduler', 'campaign_ids': [],
                                 'date_index': 0, 'batch_index': 0}, priority=71)
                    totals['advertising'] += int(is_new)
                if refresh_due(sources['feedbacks'], settings.sync_feedbacks_interval_seconds):
                    _, is_new = enqueue_sync_job(db, store=store, group='feedbacks', now=now,
                        payload={'store_id': store.id, 'origin': 'scheduler'}, priority=64)
                    totals['feedbacks'] += int(is_new)
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
