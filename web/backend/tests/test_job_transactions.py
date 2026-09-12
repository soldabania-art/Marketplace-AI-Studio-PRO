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
