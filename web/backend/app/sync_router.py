from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .db import get_db
from .marketplace_sync import latest_snapshot
from .models import MarketplaceConnection, User
from .security import get_current_user
from .store_access import resolve_store
from .sync_scheduler import enqueue_sync_job

router=APIRouter(prefix='/sync',tags=['marketplace-sync'])

@router.post('/wildberries')
def queue_wb_sync(store_id:str|None=None,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    store=resolve_store(db,user,store_id)
    connection=db.query(MarketplaceConnection).filter(MarketplaceConnection.store_id==store.id,MarketplaceConnection.marketplace=='wildberries',MarketplaceConnection.enabled.is_(True)).first()
    if not connection: raise HTTPException(409,'Wildberries не подключён к выбранному магазину.')
    job,_=enqueue_sync_job(db,store=store,group='analytics',payload={'store_id':store.id,'origin':'manual_sync'},priority=60)
    return {'queued':True,'job_id':job.id,'status':job.status.value,'store_id':store.id}

@router.get('/wildberries/status')
def wb_sync_status(store_id:str|None=None,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    store=resolve_store(db,user,store_id)
    stocks=latest_snapshot(db,store_id=store.id,marketplace='wildberries',snapshot_type='stocks')
    sales=latest_snapshot(db,store_id=store.id,marketplace='wildberries',snapshot_type='sales_velocity_7d')
    return {'store_id':store.id,'store_name':store.name,'stocks':({'snapshot_id':stocks.id,'created_at':stocks.created_at,'count':stocks.payload.get('count',0)} if stocks else None),'sales_velocity_7d':({'snapshot_id':sales.id,'created_at':sales.created_at,'count':sales.payload.get('count',0)} if sales else None)}
