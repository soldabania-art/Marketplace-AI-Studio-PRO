import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier

import pytest

from app.data_health_incidents import reconcile_health_incidents
from app.data_health import expected_coverage
from app.db import Base, SessionLocal, engine
from app.job_queue import safe_job_error
from app.models import (
    BackgroundJob,
    DataHealthIncident,
    JobStatus,
    MarketplaceConnection,
    MarketplaceSnapshot,
    Membership,
    MembershipRole,
    Store,
    User,
    Workspace,
)
from app.sync_scheduler import enqueue_sync_job, schedule_due_syncs_once

Base.metadata.create_all(bind=engine)


def _connected_store():
    db = SessionLocal()
    suffix = uuid.uuid4().hex
    user = User(email=f'scheduler-{suffix}@example.com', password_hash='test')
    workspace = Workspace(name=f'Scheduler {suffix}')
    db.add_all([user, workspace]); db.flush()
    db.add(Membership(user_id=user.id, workspace_id=workspace.id, role=MembershipRole.owner))
    store = Store(workspace_id=workspace.id, name=f'Store {suffix}')
    db.add(store); db.flush()
    db.add(MarketplaceConnection(user_id=user.id, store_id=store.id, marketplace='wildberries', encrypted_token='encrypted-test', enabled=True))
    db.commit()
    result = (workspace.id, store.id)
    db.close()
    return result


def test_job_errors_are_sanitized_before_database_storage():
    error = RuntimeError('Authorization: Bearer top-secret token=another-secret? api_key=third-secret')
    value = safe_job_error(error)
    assert value.startswith('RuntimeError:')
    assert 'top-secret' not in value
    assert 'another-secret' not in value
    assert 'third-secret' not in value
    assert '[REDACTED]' in value


def test_incidents_are_deduplicated_and_resolved_without_raw_errors():
    workspace_id, store_id = _connected_store()
    now = datetime.now(timezone.utc)
    sources = [{'key': 'stocks', 'label': 'Остатки', 'status': 'error'}]
    with SessionLocal() as db:
        first = reconcile_health_incidents(db, workspace_id=workspace_id, store_id=store_id, sources=sources, now=now)
        second = reconcile_health_incidents(db, workspace_id=workspace_id, store_id=store_id, sources=sources, now=now + timedelta(minutes=1))
        assert first['opened'] == 1
        assert second['opened'] == 0
        assert db.query(DataHealthIncident).filter(DataHealthIncident.store_id == store_id).count() == 1
        resolved = reconcile_health_incidents(db, workspace_id=workspace_id, store_id=store_id,
            sources=[{'key': 'stocks', 'label': 'Остатки', 'status': 'healthy'}], now=now + timedelta(minutes=2))
        assert resolved['resolved'] == 1
        assert db.query(DataHealthIncident).filter(DataHealthIncident.store_id == store_id, DataHealthIncident.status == 'open').count() == 0


def test_scheduler_queues_due_read_only_syncs_once_per_window_and_resolves_incidents():
    workspace_id, store_id = _connected_store()
    now = datetime.now(timezone.utc).replace(microsecond=0)
    old = now - timedelta(days=3)
    with SessionLocal() as db:
        for snapshot_type, payload in (
            ('catalog', {'count': 1}), ('stocks', {'count': 1}), ('sales_velocity_7d', {'count': 1}),
            ('finance_realization_sync', {'complete': True, 'schema_state': 'valid', 'rejected_count': 0}), ('advertising_sync', {'complete': True, 'schema_state': 'valid', 'rejected_count': 0}),
        ):
            db.add(MarketplaceSnapshot(store_id=store_id, marketplace='wildberries', snapshot_type=snapshot_type,
                payload=payload, created_at=old, source_updated_at=old))
        db.commit()

    first = schedule_due_syncs_once(now)
    second = schedule_due_syncs_once(now)
    assert first['analytics'] >= 1 and first['finance'] >= 1 and first['advertising'] >= 1
    with SessionLocal() as db:
        jobs = db.query(BackgroundJob).filter(BackgroundJob.store_id == store_id).all()
        assert {job.job_type for job in jobs} == {
            'marketplace.wb.analytics.sync', 'marketplace.wb.finance.sync',
            'marketplace.wb.advertising.sync', 'marketplace.wb.feedbacks.sync'}
        assert len(jobs) == 4
        assert all((job.payload or {}).get('origin') == 'scheduler' for job in jobs)
        assert db.query(DataHealthIncident).filter(DataHealthIncident.store_id == store_id, DataHealthIncident.status == 'open').count() == 5
        for job in jobs:
            job.status = JobStatus.succeeded; job.finished_at = now
        coverage = expected_coverage('finance', now=now + timedelta(minutes=1), period_days=30)
        for snapshot_type, payload in (
            ('catalog', {'count': 1}), ('stocks', {'count': 1}), ('sales_velocity_7d', {'count': 1}),
            ('finance_realization_sync', {**coverage, 'complete': True, 'schema_state': 'valid', 'rejected_count': 0}),
            ('advertising_sync', {**coverage, 'complete': True, 'schema_state': 'valid', 'rejected_count': 0}),
            ('feedbacks', {'count': 1, 'items': []}),
        ):
            db.add(MarketplaceSnapshot(store_id=store_id, marketplace='wildberries', snapshot_type=snapshot_type,
                payload=payload, created_at=now, source_updated_at=now))
        db.commit()
    assert second['analytics'] == 0 and second['finance'] == 0 and second['advertising'] == 0
    recovered = schedule_due_syncs_once(now + timedelta(minutes=1))
    assert recovered['incidents_resolved'] >= 5
    with SessionLocal() as db:
        assert db.query(DataHealthIncident).filter(DataHealthIncident.store_id == store_id, DataHealthIncident.status == 'open').count() == 0


def test_scheduler_refreshes_feedbacks_without_browser_and_does_not_duplicate_active_sync():
    workspace_id, store_id = _connected_store()
    now = datetime.now(timezone.utc).replace(microsecond=0)
    old = now - timedelta(days=3)
    with SessionLocal() as db:
        for snapshot_type, payload in (
            ('catalog', {'count': 1}), ('stocks', {'count': 1}), ('sales_velocity_7d', {'count': 1}),
            ('finance_realization_sync', {'complete': True, 'schema_state': 'valid', 'rejected_count': 0}), ('advertising_sync', {'complete': True, 'schema_state': 'valid', 'rejected_count': 0}),
            ('feedbacks', {'count': 1, 'items': []}),
        ):
            db.add(MarketplaceSnapshot(store_id=store_id, marketplace='wildberries', snapshot_type=snapshot_type,
                payload=payload, created_at=old, source_updated_at=old))
        active = BackgroundJob(
            workspace_id=workspace_id,
            store_id=store_id,
            job_type='marketplace.wb.analytics.sync',
            idempotency_key=f'manual-wb-analytics:{store_id}',
            payload={'store_id': store_id, 'origin': 'manual'},
            status=JobStatus.running,
        )
        db.add(active)
        db.commit()

    result = schedule_due_syncs_once(now)

    assert result['analytics'] == 0
    assert result['feedbacks'] == 1
    with SessionLocal() as db:
        analytics = db.query(BackgroundJob).filter(
            BackgroundJob.store_id == store_id,
            BackgroundJob.job_type == 'marketplace.wb.analytics.sync',
            BackgroundJob.status.in_([JobStatus.queued, JobStatus.running, JobStatus.retry]),
        ).all()
        feedbacks = db.query(BackgroundJob).filter(
            BackgroundJob.store_id == store_id,
            BackgroundJob.job_type == 'marketplace.wb.feedbacks.sync',
        ).all()
        assert len(analytics) == 1
        assert len(feedbacks) == 1
        assert feedbacks[0].payload['origin'] == 'scheduler'


def test_finance_recovery_runs_receive_distinct_page_namespaces():
    workspace_id, store_id = _connected_store()
    now = datetime.now(timezone.utc).replace(microsecond=0)
    old = now - timedelta(days=3)
    with SessionLocal() as db:
        for snapshot_type, payload in (
            ('catalog', {'count': 1}), ('stocks', {'count': 1}), ('sales_velocity_7d', {'count': 1}),
            ('finance_realization_sync', {'complete': True, 'schema_state': 'valid', 'rejected_count': 0}), ('advertising_sync', {'complete': True, 'schema_state': 'valid', 'rejected_count': 0}),
            ('feedbacks', {'count': 1, 'items': []}),
        ):
            db.add(MarketplaceSnapshot(store_id=store_id, marketplace='wildberries', snapshot_type=snapshot_type,
                payload=payload, created_at=old, source_updated_at=old))
        db.add(BackgroundJob(
            workspace_id=workspace_id, store_id=store_id, job_type='marketplace.wb.finance.sync',
            idempotency_key=f'failed-finance:{store_id}', payload={'store_id': store_id},
            status=JobStatus.dead, created_at=old, finished_at=old,
        ))
        db.commit()

    schedule_due_syncs_once(now)
    with SessionLocal() as db:
        first = db.query(BackgroundJob).filter(
            BackgroundJob.store_id == store_id,
            BackgroundJob.job_type == 'marketplace.wb.finance.sync',
            BackgroundJob.status == JobStatus.queued,
        ).order_by(BackgroundJob.created_at.desc()).first()
        first_run_id = first.payload['run_id']
        first.status = JobStatus.dead
        first.finished_at = now
        db.commit()

    schedule_due_syncs_once(now + timedelta(hours=1))
    with SessionLocal() as db:
        second = db.query(BackgroundJob).filter(
            BackgroundJob.store_id == store_id,
            BackgroundJob.job_type == 'marketplace.wb.finance.sync',
            BackgroundJob.status == JobStatus.queued,
        ).order_by(BackgroundJob.created_at.desc()).first()
        assert second.payload['run_id'] != first_run_id
        assert first_run_id in first.idempotency_key
        assert second.payload['run_id'] in second.idempotency_key


@pytest.mark.skipif(engine.dialect.name != 'postgresql', reason='concurrent root sync admission requires PostgreSQL advisory locks')
def test_concurrent_root_sync_admission_reuses_one_active_job_postgresql():
    _, store_id = _connected_store()
    barrier = Barrier(2)
    now = datetime.now(timezone.utc).replace(microsecond=0)

    def admit(origin):
        with SessionLocal() as db:
            store = db.get(Store, store_id)
            barrier.wait(timeout=5)
            job, created = enqueue_sync_job(
                db,
                store=store,
                group='analytics',
                now=now,
                payload={'store_id': store.id, 'origin': origin},
                priority=55,
            )
            return job.id, created

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(admit, ('scheduler', 'browser')))

    assert len({job_id for job_id, _ in results}) == 1
    assert sum(int(created) for _, created in results) == 1
    with SessionLocal() as db:
        active = db.query(BackgroundJob).filter(
            BackgroundJob.store_id == store_id,
            BackgroundJob.job_type == 'marketplace.wb.analytics.sync',
            BackgroundJob.status.in_([JobStatus.queued, JobStatus.running, JobStatus.retry]),
        ).all()
        assert len(active) == 1
