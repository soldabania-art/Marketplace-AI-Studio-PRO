import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier, local

import pytest
from fastapi.testclient import TestClient

from app.db import Base, SessionLocal, engine
from app.main import app
from app.models import BackgroundJob, JobStatus, MarketplaceConnection


Base.metadata.create_all(bind=engine)
client = TestClient(app)


def _connected_owner():
    response = client.post('/api/v1/auth/register', json={
        'email': f'wb02-{uuid.uuid4().hex}@example.com',
        'password': 'StrongPass123!',
        'workspace_name': 'WB02 recovery',
    })
    assert response.status_code == 201
    headers = {'Authorization': f"Bearer {response.json()['access_token']}"}
    user_id = client.get('/api/v1/auth/me', headers=headers).json()['id']
    store_id = client.get('/api/v1/stores', headers=headers).json()['stores'][0]['id']
    with SessionLocal() as db:
        db.add(MarketplaceConnection(
            user_id=user_id,
            store_id=store_id,
            marketplace='wildberries',
            encrypted_token='test',
            enabled=True,
            capability_results={'summary': 'complete', 'sources': [
                {'key': key, 'status': 'available', 'endpoints': []}
                for key in ('catalog', 'analytics', 'finance', 'advertising', 'feedbacks')
            ]},
        ))
        db.commit()
    return headers, store_id


@pytest.mark.parametrize('source', ['finance', 'advertising'])
def test_manual_import_recovers_dead_continuation_as_one_new_deduplicated_run(source):
    headers, store_id = _connected_owner()

    first = client.post(f'/api/v1/onboarding/import?store_id={store_id}', headers=headers)
    assert first.status_code == 202
    first_ids = {key: value['id'] for key, value in first.json()['jobs'].items()}

    with SessionLocal() as db:
        roots = db.query(BackgroundJob).filter(BackgroundJob.id.in_(first_ids.values())).all()
        for root in roots:
            root.status = JobStatus.succeeded
        failed_root = db.get(BackgroundJob, first_ids[source])
        if source == 'finance':
            continuation_key = f"wb-finance:{store_id}:{failed_root.payload['run_id']}:77"
            continuation_payload = {
                'store_id': store_id, 'date_from': failed_root.payload['date_from'],
                'date_to': failed_root.payload['date_to'], 'rrd_id': 77,
                'page_number': 2, 'run_id': failed_root.payload['run_id'],
            }
        else:
            continuation_key = f"wb-ads:{store_id}:{failed_root.payload['run_id']}:1:0"
            continuation_payload = {
                'store_id': store_id, 'date_from': failed_root.payload['date_from'],
                'date_to': failed_root.payload['date_to'], 'campaign_ids': [77],
                'date_index': 1, 'batch_index': 0, 'run_id': failed_root.payload['run_id'],
            }
        dead_child = BackgroundJob(
            workspace_id=failed_root.workspace_id,
            store_id=store_id,
            job_type=f'marketplace.wb.{source}.sync',
            idempotency_key=continuation_key,
            payload=continuation_payload,
            status=JobStatus.dead,
            attempts=5,
            max_attempts=5,
        )
        db.add(dead_child)
        db.commit()
        dead_child_id = dead_child.id
        original_run_id = failed_root.payload['run_id']

    recovered = client.post(f'/api/v1/onboarding/import?store_id={store_id}', headers=headers)
    repeated = client.post(f'/api/v1/onboarding/import?store_id={store_id}', headers=headers)
    assert recovered.status_code == 202
    assert repeated.status_code == 202
    recovered_ids = {key: value['id'] for key, value in recovered.json()['jobs'].items()}
    assert set(recovered_ids) == {'core', 'finance', 'advertising'}
    assert recovered_ids[source] != first_ids[source]
    for healthy_source in {'core', 'finance', 'advertising'} - {source}:
        assert recovered_ids[healthy_source] == first_ids[healthy_source]
    assert recovered_ids == {key: value['id'] for key, value in repeated.json()['jobs'].items()}

    with SessionLocal() as db:
        recovered_job = db.get(BackgroundJob, recovered_ids[source])
        assert recovered_job.status == JobStatus.queued
        assert recovered_job.payload['run_id'] != original_run_id
        assert db.get(BackgroundJob, dead_child_id).status == JobStatus.dead
        recovered_job.status = JobStatus.dead
        recovered_job.attempts = recovered_job.max_attempts
        db.commit()

    second_recovery = client.post(f'/api/v1/onboarding/import?store_id={store_id}', headers=headers)
    second_repeated = client.post(f'/api/v1/onboarding/import?store_id={store_id}', headers=headers)
    second_id = second_recovery.json()['jobs'][source]['id']
    assert second_id != recovered_ids[source]
    assert second_repeated.json()['jobs'][source]['id'] == second_id


def test_manual_import_rolls_back_all_three_jobs_when_staging_fails(monkeypatch):
    from app import onboarding_router

    headers, store_id = _connected_owner()
    original = onboarding_router.enqueue_sync_job
    calls = 0

    def fail_third(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 3:
            raise RuntimeError('injected third enqueue failure')
        return original(*args, **kwargs)

    monkeypatch.setattr(onboarding_router, 'enqueue_sync_job', fail_third)
    response = TestClient(app, raise_server_exceptions=False).post(
        f'/api/v1/onboarding/import?store_id={store_id}', headers=headers,
    )
    assert response.status_code == 500
    with SessionLocal() as db:
        assert db.query(BackgroundJob).filter_by(store_id=store_id).count() == 0


def test_manual_import_does_not_bypass_active_retry_cooldown():
    headers, store_id = _connected_owner()
    first = client.post(f'/api/v1/onboarding/import?store_id={store_id}', headers=headers).json()
    finance_id = first['jobs']['finance']['id']
    cooldown = datetime.now(timezone.utc) + timedelta(minutes=20)
    with SessionLocal() as db:
        finance = db.get(BackgroundJob, finance_id)
        finance.status = JobStatus.retry
        finance.available_at = cooldown
        db.commit()

    repeated = client.post(f'/api/v1/onboarding/import?store_id={store_id}', headers=headers)
    assert repeated.status_code == 202
    assert repeated.json()['jobs']['finance']['id'] == finance_id
    with SessionLocal() as db:
        finance = db.get(BackgroundJob, finance_id)
        assert finance.status == JobStatus.retry
        assert finance.available_at.replace(tzinfo=timezone.utc) == cooldown
        assert db.query(BackgroundJob).filter_by(store_id=store_id).count() == 3


def test_historical_dead_run_does_not_restart_a_completed_current_run():
    headers, store_id = _connected_owner()
    current = client.post(f'/api/v1/onboarding/import?store_id={store_id}', headers=headers).json()
    current_ids = {key: item['id'] for key, item in current['jobs'].items()}
    with SessionLocal() as db:
        finance = db.get(BackgroundJob, current_ids['finance'])
        finance.status = JobStatus.succeeded
        db.add(BackgroundJob(
            workspace_id=finance.workspace_id,
            store_id=store_id,
            job_type='marketplace.wb.finance.sync',
            idempotency_key=f'wb-finance:{store_id}:onboarding:old-run:77',
            payload={'store_id': store_id, 'run_id': 'onboarding:old-run', 'rrd_id': 77},
            status=JobStatus.dead,
            attempts=5,
            max_attempts=5,
        ))
        db.commit()

    repeated = client.post(f'/api/v1/onboarding/import?store_id={store_id}', headers=headers)
    assert repeated.status_code == 202
    assert repeated.json()['jobs']['finance']['id'] == current_ids['finance']


@pytest.mark.skipif(engine.dialect.name != 'postgresql', reason='real concurrent PostgreSQL transactions')
def test_concurrent_manual_recovery_creates_only_one_three_job_generation(monkeypatch):
    from app import onboarding_router

    headers, store_id = _connected_owner()
    first = client.post(f'/api/v1/onboarding/import?store_id={store_id}', headers=headers).json()
    first_ids = [item['id'] for item in first['jobs'].values()]
    with SessionLocal() as db:
        for job in db.query(BackgroundJob).filter(BackgroundJob.id.in_(first_ids)).all():
            job.status = JobStatus.dead
            job.attempts = job.max_attempts
        db.commit()

    barrier = Barrier(2)
    thread_state = local()
    original_generation = onboarding_router._manual_group_generation

    def overlap_requests(*args, **kwargs):
        if not getattr(thread_state, 'synchronized', False):
            thread_state.synchronized = True
            barrier.wait(timeout=5)
        return original_generation(*args, **kwargs)

    monkeypatch.setattr(onboarding_router, '_manual_group_generation', overlap_requests)

    def recover(_):
        response = client.post(f'/api/v1/onboarding/import?store_id={store_id}', headers=headers)
        assert response.status_code == 202
        return {key: value['id'] for key, value in response.json()['jobs'].items()}

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(recover, range(2)))
    assert results[0] == results[1]
    with SessionLocal() as db:
        jobs = db.query(BackgroundJob).filter_by(store_id=store_id).all()
        assert len(jobs) == 6
        assert sum(job.status == JobStatus.queued for job in jobs) == 3
