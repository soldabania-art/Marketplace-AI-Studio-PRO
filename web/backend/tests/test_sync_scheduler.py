import uuid
from datetime import datetime, timedelta, timezone

from app.data_health_incidents import reconcile_health_incidents
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
from app.sync_scheduler import schedule_due_syncs_once

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
            ('finance_realization_sync', {'complete': True}), ('advertising_sync', {'complete': True}),
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
            'marketplace.wb.analytics.sync', 'marketplace.wb.finance.sync', 'marketplace.wb.advertising.sync'}
        assert len(jobs) == 3
        assert all((job.payload or {}).get('origin') == 'scheduler' for job in jobs)
        assert db.query(DataHealthIncident).filter(DataHealthIncident.store_id == store_id, DataHealthIncident.status == 'open').count() == 5
        for job in jobs:
            job.status = JobStatus.succeeded; job.finished_at = now
        for snapshot_type, payload in (
            ('catalog', {'count': 1}), ('stocks', {'count': 1}), ('sales_velocity_7d', {'count': 1}),
            ('finance_realization_sync', {'complete': True}), ('advertising_sync', {'complete': True}),
        ):
            db.add(MarketplaceSnapshot(store_id=store_id, marketplace='wildberries', snapshot_type=snapshot_type,
                payload=payload, created_at=now, source_updated_at=now))
        db.commit()
    assert second['analytics'] == 0 and second['finance'] == 0 and second['advertising'] == 0
    recovered = schedule_due_syncs_once(now + timedelta(minutes=1))
    assert recovered['incidents_resolved'] >= 5
    with SessionLocal() as db:
        assert db.query(DataHealthIncident).filter(DataHealthIncident.store_id == store_id, DataHealthIncident.status == 'open').count() == 0
