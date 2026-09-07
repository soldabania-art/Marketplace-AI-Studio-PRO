import asyncio
import hashlib
import logging
import random
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

from .config import get_settings
from .db import SessionLocal
from .fbo_service import fetch_wb_slots
from .fbo_worker import process_watch
from .job_queue import enqueue
from .marketplace_connections import decrypt_connection
from .models import BackgroundJob, FboWatch, MarketplaceConnection, Store

logger = logging.getLogger(__name__)
_LOCAL_LOCKS: dict[str, asyncio.Lock] = {}


def _group_key(store_id: str | None, user_id: str) -> tuple[str, str]:
    return ('store', store_id) if store_id else ('legacy-user', user_id)


def _lock_name(group: tuple[str, str]) -> str:
    return f'fbo:wildberries:{group[0]}:{group[1]}'


def _advisory_key(name: str) -> int:
    value = int.from_bytes(hashlib.blake2b(name.encode(), digest_size=8).digest(), 'big', signed=False)
    return value if value < 2**63 else value - 2**64


def _load_group_watches(db: Session, group: tuple[str, str]) -> list[FboWatch]:
    query = db.query(FboWatch).filter(
        FboWatch.enabled.is_(True),
        FboWatch.marketplace == 'wildberries',
    )
    if group[0] == 'store':
        query = query.filter(FboWatch.store_id == group[1])
    else:
        query = query.filter(FboWatch.store_id.is_(None), FboWatch.user_id == group[1])
    return query.all()


def _load_connection(db: Session, group: tuple[str, str]) -> MarketplaceConnection | None:
    query = db.query(MarketplaceConnection).filter(
        MarketplaceConnection.marketplace == 'wildberries',
        MarketplaceConnection.enabled.is_(True),
    )
    if group[0] == 'store':
        query = query.filter(MarketplaceConnection.store_id == group[1])
    else:
        query = query.filter(MarketplaceConnection.store_id.is_(None), MarketplaceConnection.user_id == group[1])
    return query.first()


def _seconds_since(value: datetime | None) -> float | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - value).total_seconds()


def _recently_checked(watches: list[FboWatch], minimum_interval: int) -> bool:
    timestamps = [watch.last_checked_at for watch in watches if watch.last_checked_at is not None]
    if not timestamps:
        return False
    newest = max(timestamps, key=lambda value: value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value)
    elapsed = _seconds_since(newest)
    return elapsed is not None and elapsed < minimum_interval


@asynccontextmanager
async def _account_lease(db: Session, group: tuple[str, str]):
    name = _lock_name(group)
    dialect = db.get_bind().dialect.name
    if dialect == 'postgresql':
        key = _advisory_key(name)
        acquired = bool(db.execute(text('SELECT pg_try_advisory_lock(:key)'), {'key': key}).scalar())
        try:
            yield acquired
        finally:
            if acquired:
                db.execute(text('SELECT pg_advisory_unlock(:key)'), {'key': key})
        return

    lock = _LOCAL_LOCKS.setdefault(name, asyncio.Lock())
    if lock.locked():
        yield False
        return
    await lock.acquire()
    try:
        yield True
    finally:
        lock.release()


async def process_group_job(group: tuple[str, str]) -> dict[str, int]:
    """Execute one durable FBO poll job for a store/account."""
    settings = get_settings()
    db = SessionLocal()
    stats = {'checked_accounts': 0, 'checked_watches': 0, 'pushes_sent': 0, 'skipped_locked': 0, 'skipped_recent': 0, 'missing_connection': 0, 'failures': 0}
    try:
        async with _account_lease(db, group) as acquired:
            if not acquired:
                stats['skipped_locked'] = 1
                return stats
            watches = _load_group_watches(db, group)
            if not watches:
                return stats
            minimum_interval = max(10, settings.fbo_account_min_interval_seconds)
            if _recently_checked(watches, minimum_interval):
                stats['skipped_recent'] = 1
                return stats
            connection = _load_connection(db, group)
            if not connection:
                stats['missing_connection'] = 1
                return stats
            try:
                token = decrypt_connection(connection)
                slots = await fetch_wb_slots(token)
                stats['checked_accounts'] = 1
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code if exc.response is not None else None
                logger.warning('WB slot monitor request failed group=%s status=%s', _lock_name(group), status)
                raise
            for watch in watches:
                stats['checked_watches'] += 1
                stats['pushes_sent'] += process_watch(db, watch, slots)
    finally:
        db.close()
    return stats


def _workspace_for_store(db: Session, store_id: str | None) -> str | None:
    if not store_id:
        return None
    row = db.query(Store.workspace_id).filter(Store.id == store_id).first()
    return row[0] if row else None


async def process_enabled_watches_once() -> dict[str, int]:
    """Schedule one durable FBO polling job per store/account time bucket."""
    settings = get_settings()
    db = SessionLocal()
    try:
        rows = db.query(FboWatch.store_id, FboWatch.user_id).filter(FboWatch.enabled.is_(True), FboWatch.marketplace == 'wildberries').all()
        groups = list(dict.fromkeys(_group_key(store_id, user_id) for store_id, user_id in rows))
        interval = max(10, settings.fbo_account_min_interval_seconds)
        bucket = int(datetime.now(timezone.utc).timestamp()) // interval
        enqueued = 0
        for group in groups:
            store_id = group[1] if group[0] == 'store' else None
            key = f'fbo-poll:{group[0]}:{group[1]}:{bucket}'
            before = db.query(BackgroundJob.id).filter(BackgroundJob.idempotency_key == key).first()
            enqueue(
                db,
                job_type='fbo.poll',
                idempotency_key=key,
                payload={'scope': group[0], 'id': group[1]},
                workspace_id=_workspace_for_store(db, store_id),
                store_id=store_id,
                priority=20,
                max_attempts=5,
            )
            if before is None:
                enqueued += 1
        totals = {'discovered_accounts': len(groups), 'enqueued_jobs': enqueued}
        logger.info('FBO scheduler cycle stats=%s', totals)
        return totals
    finally:
        db.close()


async def monitor_forever(stop_event: asyncio.Event) -> None:
    settings = get_settings()
    interval = max(10, settings.fbo_poll_seconds)
    jitter = max(0, settings.fbo_cycle_jitter_seconds)
    while not stop_event.is_set():
        try:
            await process_enabled_watches_once()
        except Exception:
            logger.exception('FBO scheduler cycle failed')
        timeout = interval + (random.uniform(0, jitter) if jitter else 0)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            pass
