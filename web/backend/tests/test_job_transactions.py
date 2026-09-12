"""Transaction boundaries: persisted domain rows and jobs, no provider writes."""
import asyncio
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import event

from app.db import Base, SessionLocal, engine
from app.job_queue import enqueue
from app.models import (BackgroundJob, MarketplaceConnection, MarketplaceFinancialLine,
                        MarketplaceAdvertisingLine, MarketplaceSnapshot, Store, User, Workspace)
from app.wb_finance import parse_financial_report_page
from app.wb_promotion import parse_advertising_stats_page

Base.metadata.create_all(bind=engine)
_TEST_STORES = []


@pytest.fixture(autouse=True)
def isolate_transaction_stores_from_global_scheduler():
    """Later scheduler tests must not poll connections created by fault tests."""
    start = len(_TEST_STORES)
    yield
    with SessionLocal() as db:
        db.query(MarketplaceConnection).filter(
            MarketplaceConnection.store_id.in_(_TEST_STORES[start:])
        ).update({'enabled': False}, synchronize_session=False)
        db.commit()


def make_store():
    with SessionLocal() as db:
        user = User(email=f't08b-{uuid.uuid4().hex}@example.com', password_hash='test')
        workspace = Workspace(name='T08B')
        db.add_all([user, workspace]); db.flush()
        store = Store(workspace_id=workspace.id, name='T08B store')
        db.add(store); db.flush()
        db.add(MarketplaceConnection(user_id=user.id, store_id=store.id,
            marketplace='wildberries', encrypted_token='test', enabled=True))
        db.commit()
        _TEST_STORES.append(store.id)
        return store.id, workspace.id


@pytest.mark.parametrize('fault', ['before_enqueue', 'after_enqueue', 'rollback', 'close'])
def test_uncommitted_domain_and_job_are_both_discarded(fault):
    store_id, workspace_id = make_store()
    key = f't08b:{uuid.uuid4().hex}'
    class Crash(BaseException):
        pass
    try:
        with SessionLocal() as db:
            db.add(MarketplaceSnapshot(store_id=store_id, marketplace='wildberries',
                snapshot_type='t08b-rollback', payload={'key': key}))
            if fault == 'before_enqueue':
                raise Crash()
            enqueue(db, job_type='test.t08b', idempotency_key=key,
                    store_id=store_id, workspace_id=workspace_id)
            if fault == 'after_enqueue':
                raise Crash()
            if fault == 'rollback':
                db.rollback()
    except Crash:
        pass
    with SessionLocal() as db:
        assert db.query(BackgroundJob).filter_by(idempotency_key=key).count() == 0
        assert db.query(MarketplaceSnapshot).filter_by(store_id=store_id).count() == 0


@pytest.mark.skipif(engine.dialect.name != 'postgresql', reason='independent PostgreSQL transactions')
def test_worker_cannot_see_job_or_domain_before_caller_commit():
    store_id, workspace_id = make_store()
    key = f't08b:{uuid.uuid4().hex}'
    with SessionLocal() as writer:
        writer.add(MarketplaceSnapshot(store_id=store_id, marketplace='wildberries',
            snapshot_type='t08b-visibility', payload={}))
        row = enqueue(writer, job_type='test.t08b', idempotency_key=key,
                      store_id=store_id, workspace_id=workspace_id)
        with SessionLocal() as reader:
            assert reader.get(BackgroundJob, row.id) is None
            assert reader.query(MarketplaceSnapshot).filter_by(store_id=store_id).count() == 0
        writer.commit()
    # Lost response after COMMIT: reopen a session and repeat the idempotent request.
    with SessionLocal() as retry:
        same = enqueue(retry, job_type='test.t08b', idempotency_key=key,
                       store_id=store_id, workspace_id=workspace_id)
        retry.commit()
        assert same.id == row.id
        assert retry.query(BackgroundJob).filter_by(idempotency_key=key).count() == 1
        assert retry.query(MarketplaceSnapshot).filter_by(store_id=store_id).count() == 1


@pytest.mark.skipif(engine.dialect.name != 'postgresql', reason='concurrent unique conflict on PostgreSQL')
def test_concurrent_enqueue_conflict_preserves_unrelated_caller_writes():
    store_id, workspace_id = make_store()
    key = f't08b:{uuid.uuid4().hex}'
    barrier = threading.Barrier(2)

    def write(number):
        with SessionLocal() as db:
            # PostgreSQL READ COMMITTED: both writers observe the key as missing.
            assert db.query(BackgroundJob).filter_by(idempotency_key=key).first() is None
            barrier.wait(timeout=5)
            db.add(MarketplaceSnapshot(store_id=store_id, marketplace='wildberries',
                snapshot_type=f't08b-conflict-{number}', payload={'number': number}))
            job = enqueue(db, job_type='test.t08b', idempotency_key=key,
                          store_id=store_id, workspace_id=workspace_id)
            # A conflict must never commit or roll back the enclosing transaction.
            with SessionLocal() as reader:
                assert reader.query(MarketplaceSnapshot).filter_by(
                    store_id=store_id, snapshot_type=f't08b-conflict-{number}').count() == 0
            db.commit()
            return job.id

    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(pool.map(write, [1, 2]))
    assert ids[0] == ids[1]
    with SessionLocal() as db:
        assert db.query(MarketplaceSnapshot).filter_by(store_id=store_id).count() == 2
        assert db.query(BackgroundJob).filter_by(idempotency_key=key).count() == 1


@pytest.mark.parametrize('source', ['finance', 'advertising'])
@pytest.mark.parametrize('fault', ['before_child', 'after_child'])
def test_page_and_checkpoint_roll_back_when_child_enqueue_fails(monkeypatch, source, fault):
    from app import marketplace_sync as service
    store_id, _ = make_store()
    payload = {'store_id': store_id, 'date_from': '2026-09-01', 'date_to': '2026-10-15',
               'run_id': f't08b:{uuid.uuid4().hex}', 'campaign_ids': [77]}
    async def finance(*args, **kwargs):
        return parse_financial_report_page([{'rrdId': 77, 'nmId': 5, 'forPay': '10.50',
                                             'reportDate': '2026-09-09'}])
    async def advertising(*args, **kwargs):
        return parse_advertising_stats_page([{'advertId': 77, 'days': [
            {'date': '2026-09-09', 'apps': [{'nm': [{'nmId': 5, 'sum': '10.50'}]}]}]}])
    monkeypatch.setattr(service, 'decrypt_connection', lambda _: 'test')
    monkeypatch.setattr(service, 'fetch_financial_report_page', finance)
    monkeypatch.setattr(service, 'fetch_advertising_stats', advertising)
    original = service.enqueue
    def broken_enqueue(*args, **kwargs):
        if fault == 'after_child':
            original(*args, **kwargs)
        raise RuntimeError('injected enqueue failure')
    monkeypatch.setattr(service, 'enqueue', broken_enqueue)
    handler = service.sync_wb_finance if source == 'finance' else service.sync_wb_advertising
    with pytest.raises(RuntimeError, match='injected enqueue failure'):
        asyncio.run(handler(payload))
    model = MarketplaceFinancialLine if source == 'finance' else MarketplaceAdvertisingLine
    with SessionLocal() as db:
        assert db.query(model).filter_by(store_id=store_id).count() == 0
        assert db.query(MarketplaceSnapshot).filter_by(store_id=store_id).count() == 0
        assert db.query(BackgroundJob).filter_by(store_id=store_id).count() == 0
    # Retry the same logical page: domain line, checkpoint and child appear together.
    monkeypatch.setattr(service, 'enqueue', original)
    asyncio.run(handler(payload))
    asyncio.run(handler(payload))
    with SessionLocal() as db:
        assert db.query(model).filter_by(store_id=store_id).count() == 1
        assert db.query(MarketplaceSnapshot).filter_by(store_id=store_id).count() >= 1
        assert db.query(BackgroundJob).filter_by(store_id=store_id).count() == 1


@pytest.mark.parametrize('source,job_count', [('stocks', 1), ('feedbacks', 1), ('finance_realization_sync', 2)])
def test_director_action_audit_and_jobs_share_one_commit(monkeypatch, source, job_count):
    from app.director_router import ActionRequest, execute_action
    from app.models import DirectorAction, DirectorRun, Membership, MembershipRole, OperationalAuditEvent
    store_id, workspace_id = make_store()
    with SessionLocal() as db:
        user_id = db.query(MarketplaceConnection).filter_by(store_id=store_id).one().user_id
        db.add(Membership(user_id=user_id, workspace_id=workspace_id, role=MembershipRole.owner))
        run = DirectorRun(store_id=store_id, workspace_id=workspace_id, fingerprint=uuid.uuid4().hex)
        db.add(run); db.flush()
        action = DirectorAction(run_id=run.id, store_id=store_id, workspace_id=workspace_id,
            action_key=f'source:{source}', kind='data_health',
            recommendation_payload={'can_execute': True, 'execution_type': 'read_sync'})
        db.add(action); db.commit()
        action_id = action.id

    def fail_final_commit(db):
        if any(isinstance(row, DirectorAction) and row.status == 'executing'
               for row in db.identity_map.values()):
            raise RuntimeError('injected action commit failure')

    with SessionLocal() as db:
        event.listen(db, 'before_commit', fail_final_commit)
        with pytest.raises(RuntimeError, match='injected action commit failure'):
            execute_action(action_id, ActionRequest(store_id=store_id), user=db.get(User, user_id), db=db)
        db.rollback()
        event.remove(db, 'before_commit', fail_final_commit)
    with SessionLocal() as db:
        assert db.get(DirectorAction, action_id).status == 'proposed'
        assert db.query(BackgroundJob).filter_by(store_id=store_id).count() == 0
        assert db.query(OperationalAuditEvent).filter_by(store_id=store_id).count() == 0
        result = execute_action(action_id, ActionRequest(store_id=store_id), user=db.get(User, user_id), db=db)
        replay = execute_action(action_id, ActionRequest(store_id=store_id), user=db.get(User, user_id), db=db)
        assert replay['execution'] == result['execution']
    with SessionLocal() as db:
        assert db.get(DirectorAction, action_id).status == 'executing'
        assert db.query(BackgroundJob).filter_by(store_id=store_id).count() == job_count
        assert db.query(OperationalAuditEvent).filter_by(store_id=store_id).count() == 1


@pytest.mark.skipif(engine.dialect.name != 'postgresql', reason='two real PostgreSQL workers and unique-index contention')
@pytest.mark.parametrize('source', ['finance', 'advertising'])
def test_distinct_jobs_for_same_page_retry_without_double_accounting(monkeypatch, source):
    from datetime import datetime, timezone
    from sqlalchemy.orm import Session
    from app import marketplace_sync as service
    from app.job_queue import run_one
    from app.models import JobStatus

    store_id, workspace_id = make_store()
    run_id = f't08b-parallel:{uuid.uuid4().hex}'
    payload = {'store_id': store_id, 'date_from': '2026-09-01', 'date_to': '2026-10-15',
               'run_id': run_id, 'campaign_ids': [77]}
    model = MarketplaceFinancialLine if source == 'finance' else MarketplaceAdvertisingLine
    job_type = f'marketplace.wb.{source}.sync'
    with SessionLocal() as db:
        # Isolated test database: claim only the two intended roots in this scenario.
        db.query(BackgroundJob).delete()
        roots = [enqueue(db, job_type=job_type, idempotency_key=f'{run_id}:root:{i}',
                         payload=payload, store_id=store_id, workspace_id=workspace_id, priority=0)
                 for i in range(2)]
        db.commit()
        root_ids = [row.id for row in roots]

    async def finance(*args, **kwargs):
        return parse_financial_report_page([{'rrdId': 77, 'nmId': 5, 'forPay': '10.50',
                                             'reportDate': '2026-09-09'}])
    async def advertising(*args, **kwargs):
        return parse_advertising_stats_page([{'advertId': 77, 'days': [
            {'date': '2026-09-09', 'apps': [{'nm': [{'nmId': 5, 'sum': '10.50'}]}]}]}])
    monkeypatch.setattr(service, 'decrypt_connection', lambda _: 'test')
    monkeypatch.setattr(service, 'fetch_financial_report_page', finance)
    monkeypatch.setattr(service, 'fetch_advertising_stats', advertising)

    barrier = threading.Barrier(2)
    arrivals = []
    gate = threading.Lock()
    def overlap_before_ledger_flush(db, *_):
        # Both actual handlers have read the page as absent before either inserts it.
        if not any(isinstance(row, model) and row.store_id == store_id for row in db.new):
            return
        with gate:
            first_pair = len(arrivals) < 2
            if first_pair:
                arrivals.append(threading.get_ident())
        if first_pair:
            barrier.wait(timeout=10)

    event.listen(Session, 'before_flush', overlap_before_ledger_flush)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(lambda worker=i: asyncio.run(run_one(f'page-worker-{worker}')))
                       for i in range(2)]
            assert all(future.result(timeout=20) for future in futures)
    finally:
        event.remove(Session, 'before_flush', overlap_before_ledger_flush)

    assert len(set(arrivals)) == 2
    with SessionLocal() as db:
        states = [db.get(BackgroundJob, key) for key in root_ids]
        assert sorted(row.status.value for row in states) == ['retry', 'succeeded']
        loser = next(row for row in states if row.status == JobStatus.retry)
        assert 'IntegrityError' in loser.last_error
        assert db.query(model).filter_by(store_id=store_id).count() == 1
        assert db.query(MarketplaceSnapshot).filter_by(store_id=store_id).count() == 1
        children = db.query(BackgroundJob).filter(BackgroundJob.store_id == store_id,
            BackgroundJob.id.notin_(root_ids)).all()
        assert len(children) == 1
        child_id = children[0].id
        child_payload = dict(children[0].payload)
        loser.available_at = datetime.now(timezone.utc)
        db.commit()

    # Execute the losing root through the real queue retry path, not a direct handler call.
    assert asyncio.run(run_one('page-retry-worker')) is True
    with SessionLocal() as db:
        states = [db.get(BackgroundJob, key) for key in root_ids]
        assert all(row.status == JobStatus.succeeded for row in states)
        assert sorted(row.attempts for row in states) == [1, 2]
        ledger = db.query(model).filter_by(store_id=store_id).one()
        amount = ledger.payout_kopecks if source == 'finance' else ledger.spend_kopecks
        assert amount == 1050
        children = db.query(BackgroundJob).filter(BackgroundJob.store_id == store_id,
            BackgroundJob.id.notin_(root_ids)).all()
        assert [row.id for row in children] == [child_id]
        assert children[0].payload == child_payload
        assert children[0].status == JobStatus.queued
        assert child_payload['run_id'] == run_id
        if source == 'finance':
            assert child_payload['rrd_id'] == 77 and child_payload['page_number'] == 2
        else:
            assert child_payload['date_index'] == 1 and child_payload['batch_index'] == 0
