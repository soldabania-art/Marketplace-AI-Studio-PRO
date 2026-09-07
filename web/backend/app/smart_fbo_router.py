from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .db import get_db
from .job_queue import enqueue
from .marketplace_sync import latest_snapshot
from .models import MarketplaceConnection, User
from .security import get_current_user
from .smart_fbo import SupplyInput, recommend_many
from .store_access import resolve_store
from .wb_analytics import build_network_supply_inputs

router=APIRouter(prefix='/smart-fbo',tags=['smart-fbo'])

class SupplyRow(BaseModel):
    sku:str=Field(min_length=1,max_length=160); warehouse_id:int|None=None; warehouse_name:str=Field(min_length=1,max_length=200); stock:int=Field(ge=0,le=10_000_000); avg_daily_sales:float=Field(ge=0,le=1_000_000); lead_time_days:int=Field(default=7,ge=0,le=90); target_cover_days:int=Field(default=21,ge=1,le=180); safety_days:int=Field(default=5,ge=0,le=90); acceptance_coefficient:int|None=None
class PlanRequest(BaseModel): store_id:str|None=None; rows:list[SupplyRow]=Field(min_length=1,max_length=5000)

@router.post('/plan')
def create_plan(payload:PlanRequest,current_user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    store=resolve_store(db,current_user,payload.store_id); recommendations=recommend_many([SupplyInput(**row.model_dump()) for row in payload.rows])
    return {'store_id':store.id,'store_name':store.name,'mode':'deterministic','live_marketplace_data':False,'source':'request_facts','summary':{'sku_warehouse_pairs':len(recommendations),'critical':sum(1 for r in recommendations if r['urgency']=='critical'),'ready_to_supply':sum(1 for r in recommendations if r['recommended_qty']>0 and r['acceptance_available']),'recommended_units':sum(r['recommended_qty'] for r in recommendations)},'recommendations':recommendations,'notice':'Расчёт выполнен по переданным фактам.'}

def _connection(db,store_id):
    row=db.query(MarketplaceConnection).filter(MarketplaceConnection.store_id==store_id,MarketplaceConnection.marketplace=='wildberries',MarketplaceConnection.enabled.is_(True)).first()
    if not row: raise HTTPException(409,'Сначала подключите Wildberries для выбранного магазина.')
    return row

def _queue_refresh(db,store):
    bucket=int(datetime.now(timezone.utc).timestamp()//300)
    return enqueue(db,job_type='marketplace.wb.analytics.sync',idempotency_key=f'wb-sync:{store.id}:{bucket}',payload={'store_id':store.id},workspace_id=store.workspace_id,store_id=store.id,priority=50,max_attempts=5)

@router.get('/live')
def snapshot_plan(store_id:str|None=None,lead_time_days:int=Query(default=7,ge=0,le=90),target_cover_days:int=Query(default=21,ge=1,le=180),safety_days:int=Query(default=5,ge=0,le=90),current_user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    """Fast Smart FBO read path. Never calls WB from the UI request."""
    store=resolve_store(db,current_user,store_id); _connection(db,store.id)
    stocks_snap=latest_snapshot(db,store_id=store.id,marketplace='wildberries',snapshot_type='stocks')
    sales_snap=latest_snapshot(db,store_id=store.id,marketplace='wildberries',snapshot_type='sales_velocity_7d')
    if not stocks_snap or not sales_snap:
        job=_queue_refresh(db,store)
        return {'store_id':store.id,'store_name':store.name,'marketplace':'wildberries','mode':'snapshot_pending','live_marketplace_data':False,'sync_required':True,'job_id':job.id,'recommendations':[],'notice':'Данные магазина ещё синхронизируются. Smart FBO не обращается к WB напрямую из интерфейса.'}
    stocks=list((stocks_snap.payload or {}).get('rows') or [])
    sales={int(row['nm_id']):row for row in ((sales_snap.payload or {}).get('items') or []) if row.get('nm_id') is not None}
    facts=build_network_supply_inputs(stocks,sales)
    recommendations=recommend_many([SupplyInput(sku=r['sku'],warehouse_id=None,warehouse_name='Сеть складов WB',stock=r['stock'],avg_daily_sales=r['avg_daily_sales'],lead_time_days=lead_time_days,target_cover_days=target_cover_days,safety_days=safety_days,acceptance_coefficient=None) for r in facts])
    facts_by_sku={r['sku']:r for r in facts}
    for row in recommendations:
        fact=facts_by_sku.get(row['sku'],{}); row['nm_id']=fact.get('nm_id'); row['title']=fact.get('title',''); row['orders_period']=fact.get('orders_period',0); row['sales_period_days']=fact.get('period_days',7); row['warehouse_stocks']=fact.get('warehouse_stocks',[]); row['warehouse_allocation_status']='pending_regional_demand'
    oldest=min(stocks_snap.created_at,sales_snap.created_at); age=max(0,int((datetime.now(timezone.utc)-oldest).total_seconds()))
    stale=age>900
    refresh_job=_queue_refresh(db,store) if stale else None
    return {'store_id':store.id,'store_name':store.name,'marketplace':'wildberries','mode':'deterministic_snapshot_v1','live_marketplace_data':True,'sync_required':stale,'refresh_job_id':refresh_job.id if refresh_job else None,'snapshot_age_seconds':age,'sources':{'stock_snapshot_id':stocks_snap.id,'sales_snapshot_id':sales_snap.id},'summary':{'products_with_sales_history':len(sales),'stock_rows':len(stocks),'critical':sum(1 for r in recommendations if r['urgency']=='critical'),'recommended_units':sum(r['recommended_qty'] for r in recommendations)},'recommendations':recommendations,'notice':'Расчёт выполнен из сохранённых данных WB. Интерфейс не расходует лимиты WB; устаревшие данные обновляются через очередь.'}
