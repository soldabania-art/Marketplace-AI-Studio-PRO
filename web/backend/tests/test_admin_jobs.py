from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.admin_router import _job_public, requeue_background_job
from app.models import JobStatus


class FakeDb:
    def __init__(self,row): self.row=row; self.added=[]; self.commits=0
    def get(self,model,identifier): return self.row if identifier==self.row.id else None
    def add(self,value): self.added.append(value)
    def commit(self): self.commits+=1
    def refresh(self,row): pass


def job(status=JobStatus.dead):
    now=datetime.now(timezone.utc)
    return SimpleNamespace(id='job-1',workspace_id='w1',store_id='s1',job_type='marketplace.wb.analytics.sync',idempotency_key='secret-idempotency',payload={'store_id':'s1','token':'must-not-leak'},status=status,priority=50,attempts=5,max_attempts=5,available_at=now,locked_at=now,locked_by='worker-1',last_error='provider token=[REDACTED]',created_at=now,updated_at=now,finished_at=now)


def test_job_public_hides_payload_values_and_idempotency_key():
    public=_job_public(job())
    assert public['payload_keys']==['store_id','token']
    assert 'payload' not in public
    assert 'idempotency_key' not in public
    assert 'must-not-leak' not in str(public)


def test_dead_job_can_be_requeued_and_audited():
    row=job(); db=FakeDb(row); admin=SimpleNamespace(id='admin-1')
    result=requeue_background_job('job-1',admin=admin,db=db)
    assert result['requeued'] is True
    assert result['previous_status']=='dead'
    assert row.status==JobStatus.queued
    assert row.attempts==0
    assert row.locked_by==''
    assert row.last_error==''
    assert db.commits==1
    assert len(db.added)==1


def test_running_job_cannot_be_manually_requeued():
    row=job(JobStatus.running); db=FakeDb(row)
    with pytest.raises(HTTPException) as exc:
        requeue_background_job('job-1',admin=SimpleNamespace(id='admin-1'),db=db)
    assert exc.value.status_code==409
