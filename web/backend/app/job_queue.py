import asyncio
import logging
import random
import socket
import uuid
from datetime import datetime, timedelta, timezone
from typing import Awaitable, Callable

from sqlalchemy import case, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .config import get_settings
from .db import SessionLocal
from .models import BackgroundJob, JobStatus

logger=logging.getLogger(__name__)
JobHandler=Callable[[dict],Awaitable[None]]
HANDLERS:dict[str,JobHandler]={}

def utcnow(): return datetime.now(timezone.utc)

def register_handler(job_type:str):
    def decorator(fn:JobHandler):
        HANDLERS[job_type]=fn
        return fn
    return decorator

def enqueue(db:Session,*,job_type:str,idempotency_key:str,payload:dict|None=None,workspace_id:str|None=None,store_id:str|None=None,priority:int=100,max_attempts:int=5,available_at:datetime|None=None)->BackgroundJob:
    existing=db.query(BackgroundJob).filter(BackgroundJob.idempotency_key==idempotency_key).first()
    if existing: return existing
    job=BackgroundJob(job_type=job_type,idempotency_key=idempotency_key,payload=payload or {},workspace_id=workspace_id,store_id=store_id,priority=max(0,priority),max_attempts=max(1,max_attempts),available_at=available_at or utcnow())
    db.add(job)
    try:
        db.commit(); db.refresh(job); return job
    except IntegrityError:
        db.rollback()
        existing=db.query(BackgroundJob).filter(BackgroundJob.idempotency_key==idempotency_key).first()
        if existing: return existing
        raise

def _claim_one(db:Session,worker_id:str,lease_seconds:int)->BackgroundJob|None:
    settings=get_settings(); now=utcnow(); stale=now-timedelta(seconds=lease_seconds)
    ready=or_(
        (BackgroundJob.status.in_([JobStatus.queued,JobStatus.retry]) & (BackgroundJob.available_at<=now)),
        (BackgroundJob.status==JobStatus.running) & (BackgroundJob.locked_at<stale),
    )
    query=db.query(BackgroundJob).filter(ready)
    # Paid tiers can enqueue with lower numeric priority. Aging prevents starvation:
    # after each aging window, old jobs move one priority band toward the front.
    aging=max(1,settings.job_priority_aging_seconds)
    if db.get_bind().dialect.name=='postgresql':
        age_seconds=func.extract('epoch',func.now()-BackgroundJob.created_at)
        effective=case((BackgroundJob.status==JobStatus.running,-1000),else_=BackgroundJob.priority-(age_seconds/aging))
        query=query.order_by(effective.asc(),BackgroundJob.available_at.asc(),BackgroundJob.created_at.asc()).with_for_update(skip_locked=True)
    else:
        query=query.order_by(BackgroundJob.priority.asc(),BackgroundJob.available_at.asc(),BackgroundJob.created_at.asc())
    job=query.first()
    if not job: return None
    job.status=JobStatus.running; job.locked_by=worker_id; job.locked_at=now; job.attempts+=1
    db.commit(); db.refresh(job); return job

def _finish(db:Session,job_id:str,worker_id:str):
    job=db.get(BackgroundJob,job_id)
    if not job or job.locked_by!=worker_id: return
    job.status=JobStatus.succeeded; job.finished_at=utcnow(); job.locked_at=None; job.locked_by=''; job.last_error=''; db.commit()

def _fail(db:Session,job_id:str,worker_id:str,error:Exception):
    settings=get_settings(); job=db.get(BackgroundJob,job_id)
    if not job or job.locked_by!=worker_id: return
    job.last_error=str(error)[:4000]; job.locked_at=None; job.locked_by=''
    if job.attempts>=job.max_attempts:
        job.status=JobStatus.dead; job.finished_at=utcnow()
    else:
        base=max(1,settings.job_retry_base_seconds); cap=max(base,settings.job_retry_max_seconds)
        delay=min(cap,base*(2**max(0,job.attempts-1)))+random.uniform(0,min(base,10))
        job.status=JobStatus.retry; job.available_at=utcnow()+timedelta(seconds=delay)
    db.commit()

async def run_one(worker_id:str)->bool:
    db=SessionLocal()
    try: job=_claim_one(db,worker_id,max(30,get_settings().job_lease_seconds))
    finally: db.close()
    if not job: return False
    handler=HANDLERS.get(job.job_type)
    if not handler:
        db=SessionLocal()
        try: _fail(db,job.id,worker_id,RuntimeError(f'No handler registered for {job.job_type}'))
        finally: db.close()
        return True
    try:
        await handler(dict(job.payload or {}))
        db=SessionLocal()
        try: _finish(db,job.id,worker_id)
        finally: db.close()
    except Exception as exc:
        logger.exception('Background job failed id=%s type=%s attempt=%s',job.id,job.job_type,job.attempts)
        db=SessionLocal()
        try: _fail(db,job.id,worker_id,exc)
        finally: db.close()
    return True

async def job_worker_forever(stop_event:asyncio.Event)->None:
    settings=get_settings(); worker_id=f'{socket.gethostname()}:{uuid.uuid4().hex[:10]}'
    semaphore=asyncio.Semaphore(max(1,settings.job_worker_concurrency))
    async def execute():
        async with semaphore: return await run_one(worker_id)
    while not stop_event.is_set():
        batch=[asyncio.create_task(execute()) for _ in range(max(1,settings.job_worker_concurrency))]
        results=await asyncio.gather(*batch,return_exceptions=True)
        did_work=any(result is True for result in results)
        if not did_work:
            try: await asyncio.wait_for(stop_event.wait(),timeout=max(.2,settings.job_idle_poll_seconds))
            except asyncio.TimeoutError: pass
