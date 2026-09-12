import asyncio
import logging
import random
import re
import socket
import threading
import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Awaitable, Callable

from sqlalchemy import case, event, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from .config import get_settings
from .db import SessionLocal
from .models import BackgroundJob, JobStatus

logger = logging.getLogger(__name__)
JobHandler = Callable[[dict], Awaitable[None]]
HANDLERS: dict[str, JobHandler] = {}


class JobOwnershipLost(RuntimeError):
    """The handler belongs to an attempt that is no longer current."""


@dataclass(frozen=True)
class JobAttempt:
    job_id: str
    worker_id: str
    attempt_id: str
    attempt_number: int
    ownership_lost: threading.Event = field(repr=False, compare=False)


_CURRENT_ATTEMPT: ContextVar[JobAttempt | None] = ContextVar("current_job_attempt", default=None)


def current_job_attempt() -> JobAttempt:
    attempt = _CURRENT_ATTEMPT.get()
    if attempt is None:
        raise RuntimeError("No background job attempt is active")
    return attempt


_SECRET_PATTERNS = (
    (re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s,;]+"), r"\1[REDACTED]"),
    (re.compile(r"(?i)((?:api[_-]?key|token|secret|password)\s*[:=]\s*)[^\s,;]+"), r"\1[REDACTED]"),
    (re.compile(r"(?i)([?&](?:api[_-]?key|token|secret|password)=)[^&\s]+"), r"\1[REDACTED]"),
)


def safe_job_error(error: Exception) -> str:
    """Return operational context without persisting credentials from provider errors."""
    value = str(error).replace("\r", " ").replace("\n", " ")
    for pattern, replacement in _SECRET_PATTERNS:
        value = pattern.sub(replacement, value)
    return f"{type(error).__name__}: {value}"[:1000]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def register_handler(job_type: str):
    def decorator(fn: JobHandler):
        HANDLERS[job_type] = fn
        return fn
    return decorator


@event.listens_for(Session, "before_commit")
def _fence_handler_commit(db: Session) -> None:
    """Reject ORM writes made by an attempt after its lease was replaced."""
    attempt = _CURRENT_ATTEMPT.get()
    if attempt is None:
        return
    if attempt.ownership_lost.is_set():
        raise JobOwnershipLost(f"Job attempt {attempt.attempt_id} lost ownership")
    # Keep ownership stable through the actual COMMIT/ROLLBACK. A plain SELECT
    # permits another worker to replace the attempt after this check.
    # Acquire the fence before pending ORM writes can autoflush.
    with db.no_autoflush:
        owned = db.execute(
            select(BackgroundJob.id).where(
                BackgroundJob.id == attempt.job_id,
                BackgroundJob.status == JobStatus.running,
                BackgroundJob.locked_by == attempt.worker_id,
                BackgroundJob.attempt_id == attempt.attempt_id,
            ).with_for_update()
        ).scalar_one_or_none()
    if owned is None:
        attempt.ownership_lost.set()
        raise JobOwnershipLost(f"Job attempt {attempt.attempt_id} is stale")


def enqueue(
    db: Session,
    *,
    job_type: str,
    idempotency_key: str,
    payload: dict | None = None,
    workspace_id: str | None = None,
    store_id: str | None = None,
    priority: int = 100,
    max_attempts: int = 5,
    available_at: datetime | None = None,
) -> BackgroundJob:
    """Stage a durable job in the caller's transaction; never commit or roll back.

    PostgreSQL is the production outbox: domain state and BackgroundJob become
    visible together at caller COMMIT. A unique-key conflict affects only this
    INSERT, never the caller's other writes. SQLite supports the same contract
    for development (its concurrency is not the production guarantee).
    """
    dialect = db.get_bind().dialect.name
    insert = {"postgresql": pg_insert, "sqlite": sqlite_insert}.get(dialect)
    if insert is None:
        raise RuntimeError(f"Transactional enqueue is unsupported on {dialect}")
    _fence_handler_commit(db)
    # Pending parent/domain objects and this INSERT share the outer transaction.
    db.flush()
    db.execute(insert(BackgroundJob).values(
        job_type=job_type,
        idempotency_key=idempotency_key,
        payload=payload or {},
        workspace_id=workspace_id,
        store_id=store_id,
        priority=max(0, priority),
        max_attempts=max(1, max_attempts),
        available_at=available_at or utcnow(),
    ).on_conflict_do_nothing(index_elements=["idempotency_key"]))
    return db.query(BackgroundJob).filter(
        BackgroundJob.idempotency_key == idempotency_key
    ).one()


def _claim_one(
    db: Session,
    worker_id: str,
    lease_seconds: int,
    *,
    now: datetime | None = None,
) -> BackgroundJob | None:
    settings = get_settings()
    current = now or utcnow()
    stale = current - timedelta(seconds=max(1, lease_seconds))
    lease_timestamp = func.coalesce(BackgroundJob.heartbeat_at, BackgroundJob.locked_at)
    ready = or_(
        BackgroundJob.status.in_([JobStatus.queued, JobStatus.retry]) & (BackgroundJob.available_at <= current),
        (BackgroundJob.status == JobStatus.running) & (lease_timestamp < stale),
    )
    query = db.query(BackgroundJob).filter(ready)
    aging = max(1, settings.job_priority_aging_seconds)
    if db.get_bind().dialect.name == "postgresql":
        age_seconds = func.extract("epoch", func.now() - BackgroundJob.created_at)
        effective = case(
            (BackgroundJob.status == JobStatus.running, -1000),
            else_=BackgroundJob.priority - (age_seconds / aging),
        )
        query = query.order_by(
            effective.asc(), BackgroundJob.available_at.asc(), BackgroundJob.created_at.asc()
        ).with_for_update(skip_locked=True)
    else:
        query = query.order_by(
            BackgroundJob.priority.asc(), BackgroundJob.available_at.asc(), BackgroundJob.created_at.asc()
        )
    job = query.first()
    if not job:
        return None
    job.status = JobStatus.running
    job.locked_by = worker_id
    job.locked_at = current
    job.heartbeat_at = current
    job.attempt_id = str(uuid.uuid4())
    job.attempts += 1
    db.commit()
    db.refresh(job)
    return job


def _heartbeat(
    job_id: str,
    worker_id: str,
    attempt_id: str,
    *,
    now: datetime | None = None,
) -> bool:
    current = now or utcnow()
    with SessionLocal() as db:
        changed = db.execute(
            update(BackgroundJob)
            .where(
                BackgroundJob.id == job_id,
                BackgroundJob.status == JobStatus.running,
                BackgroundJob.locked_by == worker_id,
                BackgroundJob.attempt_id == attempt_id,
            )
            .values(locked_at=current, heartbeat_at=current)
        ).rowcount
        db.commit()
        return changed == 1


def _finish(db: Session, job_id: str, worker_id: str, attempt_id: str) -> bool:
    job = db.query(BackgroundJob).filter(
        BackgroundJob.id == job_id,
        BackgroundJob.status == JobStatus.running,
        BackgroundJob.locked_by == worker_id,
        BackgroundJob.attempt_id == attempt_id,
    ).with_for_update().first()
    if not job:
        db.rollback()
        return False
    job.status = JobStatus.succeeded
    job.finished_at = utcnow()
    job.locked_at = None
    job.heartbeat_at = None
    job.locked_by = ""
    job.attempt_id = ""
    job.last_error = ""
    db.commit()
    return True


def _fail(
    db: Session,
    job_id: str,
    worker_id: str,
    attempt_id: str,
    error: Exception,
) -> bool:
    settings = get_settings()
    job = db.query(BackgroundJob).filter(
        BackgroundJob.id == job_id,
        BackgroundJob.status == JobStatus.running,
        BackgroundJob.locked_by == worker_id,
        BackgroundJob.attempt_id == attempt_id,
    ).with_for_update().first()
    if not job:
        db.rollback()
        return False
    job.last_error = safe_job_error(error)
    job.locked_at = None
    job.heartbeat_at = None
    job.locked_by = ""
    job.attempt_id = ""
    if job.attempts >= job.max_attempts:
        job.status = JobStatus.dead
        job.finished_at = utcnow()
    else:
        base = max(1, settings.job_retry_base_seconds)
        cap = max(base, settings.job_retry_max_seconds)
        delay = min(cap, base * (2 ** max(0, job.attempts - 1))) + random.uniform(0, min(base, 10))
        job.status = JobStatus.retry
        job.available_at = utcnow() + timedelta(seconds=delay)
    db.commit()
    return True


def _heartbeat_loop(attempt: JobAttempt, stop_event: threading.Event, interval_seconds: float) -> None:
    while not stop_event.wait(interval_seconds):
        try:
            if not _heartbeat(attempt.job_id, attempt.worker_id, attempt.attempt_id):
                attempt.ownership_lost.set()
                return
        except Exception:
            attempt.ownership_lost.set()
            logger.exception("Job heartbeat failed id=%s attempt=%s", attempt.job_id, attempt.attempt_id)
            return


async def run_one(
    worker_id: str,
    *,
    lease_seconds: int | None = None,
    heartbeat_seconds: float | None = None,
) -> bool:
    settings = get_settings()
    lease = max(1, lease_seconds) if lease_seconds is not None else max(30, settings.job_lease_seconds)
    db = SessionLocal()
    try:
        job = _claim_one(db, worker_id, lease)
    finally:
        db.close()
    if not job:
        return False
    handler = HANDLERS.get(job.job_type)
    if not handler:
        db = SessionLocal()
        try:
            _fail(db, job.id, worker_id, job.attempt_id, RuntimeError(f"No handler registered for {job.job_type}"))
        finally:
            db.close()
        return True

    lost = threading.Event()
    attempt = JobAttempt(job.id, worker_id, job.attempt_id, job.attempts, lost)
    stop_heartbeat = threading.Event()
    configured = max(0.1, float(settings.job_heartbeat_seconds))
    heartbeat_interval = (
        max(0.05, float(heartbeat_seconds))
        if heartbeat_seconds is not None
        else min(configured, max(0.1, lease / 3))
    )
    heartbeat_thread = threading.Thread(
        target=_heartbeat_loop,
        args=(attempt, stop_heartbeat, heartbeat_interval),
        name=f"job-heartbeat-{job.id[:8]}",
        daemon=True,
    )
    heartbeat_thread.start()
    context_token = _CURRENT_ATTEMPT.set(attempt)
    error: Exception | None = None
    try:
        await handler(dict(job.payload or {}))
    except Exception as exc:
        error = exc
        logger.error(
            "Background job failed id=%s type=%s attempt=%s error_type=%s",
            job.id,
            job.job_type,
            job.attempts,
            type(exc).__name__,
        )
    finally:
        _CURRENT_ATTEMPT.reset(context_token)
        stop_heartbeat.set()
        heartbeat_thread.join(timeout=max(1.0, heartbeat_interval + 0.5))

    db = SessionLocal()
    try:
        if error is None:
            _finish(db, job.id, worker_id, job.attempt_id)
        else:
            _fail(db, job.id, worker_id, job.attempt_id, error)
    finally:
        db.close()
    return True


async def job_worker_forever(stop_event: asyncio.Event) -> None:
    settings = get_settings()
    worker_id = f"{socket.gethostname()}:{uuid.uuid4().hex[:10]}"
    semaphore = asyncio.Semaphore(max(1, settings.job_worker_concurrency))

    async def execute():
        async with semaphore:
            return await run_one(worker_id)

    while not stop_event.is_set():
        batch = [asyncio.create_task(execute()) for _ in range(max(1, settings.job_worker_concurrency))]
        results = await asyncio.gather(*batch, return_exceptions=True)
        did_work = any(result is True for result in results)
        if not did_work:
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=max(0.2, settings.job_idle_poll_seconds))
            except asyncio.TimeoutError:
                pass

