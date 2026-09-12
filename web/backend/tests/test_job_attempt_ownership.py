import asyncio
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.db import Base, SessionLocal, engine
from app.job_queue import (
    HANDLERS,
    JobOwnershipLost,
    _claim_one,
    _fail,
    _finish,
    _heartbeat,
    current_job_attempt,
    enqueue,
    run_one,
)
from app.models import BackgroundJob, JobStatus, MarketplaceSnapshot, Store, Workspace


Base.metadata.create_all(bind=engine)


def _empty_jobs() -> None:
    with SessionLocal() as db:
        db.query(BackgroundJob).delete()
        db.commit()


def _store() -> tuple[str, str]:
    suffix = uuid.uuid4().hex
    with SessionLocal() as db:
        workspace = Workspace(name=f"T08A {suffix}")
        db.add(workspace)
        db.flush()
        store = Store(workspace_id=workspace.id, name=f"Store {suffix}")
        db.add(store)
        db.commit()
        return workspace.id, store.id


def _job(job_type: str, *, workspace_id: str | None = None, store_id: str | None = None) -> str:
    with SessionLocal() as db:
        row = enqueue(
            db,
            job_type=job_type,
            idempotency_key=f"t08a:{uuid.uuid4().hex}",
            payload={"store_id": store_id} if store_id else {},
            workspace_id=workspace_id,
            store_id=store_id,
            priority=0,
            max_attempts=5,
        )
        return row.id


def test_controlled_heartbeat_prevents_300_second_reclaim_then_crash_recovers():
    _empty_jobs()
    job_id = _job("test.t08a.controlled")
    started = datetime.now(timezone.utc)

    with SessionLocal() as first_db:
        first = _claim_one(first_db, "worker-a", 300, now=started)
        first_attempt = first.attempt_id
    assert _heartbeat(job_id, "worker-a", first_attempt, now=started + timedelta(seconds=250))

    with SessionLocal() as second_db:
        assert _claim_one(second_db, "worker-b", 300, now=started + timedelta(seconds=301)) is None
    with SessionLocal() as second_db:
        recovered = _claim_one(second_db, "worker-b", 300, now=started + timedelta(seconds=551))
        second_attempt = recovered.attempt_id

    assert second_attempt != first_attempt
    assert recovered.attempts == 2
    with SessionLocal() as stale_db:
        assert _finish(stale_db, job_id, "worker-a", first_attempt) is False
        assert _fail(stale_db, job_id, "worker-a", first_attempt, RuntimeError("late failure")) is False
    with SessionLocal() as owner_db:
        assert _finish(owner_db, job_id, "worker-b", second_attempt) is True


def test_heartbeat_runs_when_handler_blocks_its_event_loop():
    _empty_jobs()
    job_type = f"test.t08a.blocking.{uuid.uuid4().hex[:10]}"
    job_id = _job(job_type)
    entered = threading.Event()
    release = threading.Event()

    async def blocking_handler(_payload):
        entered.set()
        release.wait(timeout=5)

    previous = HANDLERS.get(job_type)
    HANDLERS[job_type] = blocking_handler
    worker = threading.Thread(
        target=lambda: asyncio.run(run_one("worker-a", lease_seconds=1, heartbeat_seconds=0.1)),
        daemon=True,
    )
    try:
        worker.start()
        assert entered.wait(timeout=3)
        with SessionLocal() as db:
            initial = db.get(BackgroundJob, job_id).heartbeat_at
        time.sleep(1.25)
        with SessionLocal() as db:
            current = db.get(BackgroundJob, job_id)
            assert current.heartbeat_at > initial
            assert _claim_one(db, "worker-b", 1) is None
    finally:
        release.set()
        worker.join(timeout=5)
        if previous is None:
            HANDLERS.pop(job_type, None)
        else:
            HANDLERS[job_type] = previous
    assert not worker.is_alive()


@pytest.mark.skipif(
    engine.dialect.name != "postgresql",
    reason="stale attempt domain fencing requires two real PostgreSQL workers",
)
def test_two_workers_fence_stale_status_domain_write_and_child_enqueue():
    _empty_jobs()
    workspace_id, store_id = _store()
    job_type = f"test.t08a.fencing.{uuid.uuid4().hex[:10]}"
    job_id = _job(job_type, workspace_id=workspace_id, store_id=store_id)
    first_entered = threading.Event()
    release_first = threading.Event()
    stale_errors: list[type[Exception]] = []

    async def handler(_payload):
        attempt = current_job_attempt()
        if attempt.attempt_number == 1:
            first_entered.set()
            await asyncio.to_thread(release_first.wait, 5)
            try:
                with SessionLocal() as db:
                    db.add(MarketplaceSnapshot(
                        store_id=store_id,
                        marketplace="wildberries",
                        snapshot_type="t08a-old-worker",
                        payload={"attempt_id": attempt.attempt_id},
                    ))
                    enqueue(
                        db,
                        job_type="test.t08a.child",
                        idempotency_key=f"t08a-old-child:{job_id}",
                        payload={"parent": job_id},
                        workspace_id=workspace_id,
                        store_id=store_id,
                    )
            except JobOwnershipLost as exc:
                stale_errors.append(type(exc))
                raise
        else:
            with SessionLocal() as db:
                db.add(MarketplaceSnapshot(
                    store_id=store_id,
                    marketplace="wildberries",
                    snapshot_type="t08a-new-worker",
                    payload={"attempt_id": attempt.attempt_id},
                ))
                enqueue(
                    db,
                    job_type="test.t08a.child",
                    idempotency_key=f"t08a-new-child:{job_id}",
                    payload={"parent": job_id},
                    workspace_id=workspace_id,
                    store_id=store_id,
                )

    previous = HANDLERS.get(job_type)
    HANDLERS[job_type] = handler

    stale_worker = threading.Thread(
        target=lambda: asyncio.run(run_one("worker-a", lease_seconds=1, heartbeat_seconds=60)),
        name="t08a-worker-a",
        daemon=True,
    )
    try:
        stale_worker.start()
        assert first_entered.wait(timeout=3)
        with SessionLocal() as db:
            row = db.query(BackgroundJob).filter(BackgroundJob.id == job_id).with_for_update().one()
            row.heartbeat_at = datetime.now(timezone.utc) - timedelta(seconds=5)
            row.locked_at = row.heartbeat_at
            db.commit()
        assert asyncio.run(run_one("worker-b", lease_seconds=1, heartbeat_seconds=0.1)) is True
        release_first.set()
        stale_worker.join(timeout=5)
    finally:
        release_first.set()
        stale_worker.join(timeout=5)
        if previous is None:
            HANDLERS.pop(job_type, None)
        else:
            HANDLERS[job_type] = previous

    assert not stale_worker.is_alive()

    with SessionLocal() as db:
        parent = db.get(BackgroundJob, job_id)
        snapshots = db.query(MarketplaceSnapshot).filter(
            MarketplaceSnapshot.store_id == store_id,
            MarketplaceSnapshot.snapshot_type.in_(["t08a-old-worker", "t08a-new-worker"]),
        ).all()
        children = db.query(BackgroundJob).filter(
            BackgroundJob.idempotency_key.in_([f"t08a-old-child:{job_id}", f"t08a-new-child:{job_id}"])
        ).all()

    assert parent.status == JobStatus.succeeded
    assert parent.attempts == 2
    assert [row.snapshot_type for row in snapshots] == ["t08a-new-worker"]
    assert [row.idempotency_key for row in children] == [f"t08a-new-child:{job_id}"]
    assert stale_errors == [JobOwnershipLost]


@pytest.mark.skipif(engine.dialect.name != "postgresql", reason="requires PostgreSQL row locks")
@pytest.mark.parametrize("commit_result", [True, False])
def test_ownership_is_held_until_domain_transaction_ends(commit_result):
    from concurrent.futures import ThreadPoolExecutor
    from sqlalchemy import event
    from app.job_queue import JobAttempt, _CURRENT_ATTEMPT

    _empty_jobs()
    workspace_id, store_id = _store()
    job_id = _job("test.t08a.commit-race", workspace_id=workspace_id, store_id=store_id)
    started = datetime.now(timezone.utc)
    with SessionLocal() as db:
        owner = _claim_one(db, "worker-a", 300, now=started)
        attempt = JobAttempt(job_id, "worker-a", owner.attempt_id, owner.attempts, threading.Event())

    def try_reclaim():
        with SessionLocal() as other:
            claimed = _claim_one(other, "worker-b", 300, now=started + timedelta(seconds=301))
            return claimed.id if claimed else None

    class RollbackProbe(Exception):
        pass

    # This listener runs after the global ownership check, before actual COMMIT.
    def after_fence(db):
        with ThreadPoolExecutor(max_workers=1) as pool:
            assert pool.submit(try_reclaim).result(timeout=5) is None
        if not commit_result:
            raise RollbackProbe()

    with SessionLocal() as db:
        event.listen(db, "before_commit", after_fence)
        token = _CURRENT_ATTEMPT.set(attempt)
        try:
            db.add(MarketplaceSnapshot(
                store_id=store_id, marketplace="wildberries",
                snapshot_type="t08a-commit-race", payload={"owner": "worker-a"},
            ))
            if commit_result:
                db.commit()
            else:
                with pytest.raises(RollbackProbe):
                    db.commit()
                db.rollback()
        finally:
            _CURRENT_ATTEMPT.reset(token)
            event.remove(db, "before_commit", after_fence)

    # Both COMMIT and ROLLBACK must release the fence; a crashed lease is recoverable.
    assert try_reclaim() == job_id
    with SessionLocal() as db:
        count = db.query(MarketplaceSnapshot).filter(
            MarketplaceSnapshot.store_id == store_id,
            MarketplaceSnapshot.snapshot_type == "t08a-commit-race",
        ).count()
        assert count == int(commit_result)
