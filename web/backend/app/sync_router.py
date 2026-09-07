from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .db import get_db
from .job_queue import enqueue
from .marketplace_sync import latest_snapshot
from .models import MarketplaceConnection, User
from .security import get_current_user
from .store_access import resolve_store

router=APIRouter(prefix='/sync',tags=['marketplace-sync'])

@router.post('/wildberries')
def queue_wb_sync(store_id:str|None=None,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    store=resolve_store(db,user,store_id)
    connection=db.query(MarketplaceConnection).filter(MarketplaceConnection.store_id==store.id,MarketplaceConnection.marketplace=='wildberries',MarketplaceConnection.enabled.is_(True)).first()
    if not connection: raise HTTPException(409,'Wildberries не подключён к выбранному магазину.')
    bucket=int(datetime.now(timezone.utc).timestamp()//300)
    job=enqueue(db,job_type='marketplace.wb.analytics.sync',idempotency_key=f'wb-sync:{store.id}:{bucket}',payload={'store_id':store.id},workspace_id=store.workspace_id,store_id=store.id,priority=60,max_attempts=5)
    return {'queued':True,'job_id':job.id,'status':job.status.value,'store_id':store.id}

@router.get('/wildberries/status')
def wb_sync_status(store_id:str|None=None,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    store=resolve_store(db,user,store_id)
    stocks=latest_snapshot(db,store_id=store.id,marketplace='wildberries',snapshot_type='stocks')
    sales=latest_snapshot(db,store_id=store.id,marketplace='wildberries',snapshot_type='sales_velocity_7d')
    return {'store_id':store.id,'store_name':store.name,'stocks':({'snapshot_id':stocks.id,'created_at':stocks.created_at,'count':stocks.payload.get('count',0)} if stocks else None),'sales_velocity_7d':({'snapshot_id':sales.id,'created_at':sales.created_at,'count':sales.payload.get('count',0)} if sales else None)}
