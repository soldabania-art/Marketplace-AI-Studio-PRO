from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .db import get_db
from .config import get_settings
from .data_health import evaluate_source_snapshot, refresh_due
from .marketplace_sync import latest_snapshot
from .models import MarketplaceConnection, User
from .security import get_current_user
from .store_access import resolve_store
from .sync_scheduler import enqueue_sync_job
from .wb_analytics import build_network_supply_inputs

router=APIRouter(prefix='/seller-data',tags=['seller-data'])


def _connection(db:Session,store_id:str):
    row=db.query(MarketplaceConnection).filter(MarketplaceConnection.store_id==store_id,MarketplaceConnection.marketplace=='wildberries',MarketplaceConnection.enabled.is_(True)).first()
    if not row: raise HTTPException(409,'Wildberries не подключён к выбранному магазину.')
    return row


def _refresh(db:Session,store):
    job,_=enqueue_sync_job(db,store=store,group='analytics',payload={'store_id':store.id,'origin':'seller_data'},priority=55)
    return job


def _facts(db:Session,store):
    stocks=latest_snapshot(db,store_id=store.id,marketplace='wildberries',snapshot_type='stocks')
    sales=latest_snapshot(db,store_id=store.id,marketplace='wildberries',snapshot_type='sales_velocity_7d')
    catalog=latest_snapshot(db,store_id=store.id,marketplace='wildberries',snapshot_type='catalog')
    now=datetime.now(timezone.utc)
    health={
        'stocks':evaluate_source_snapshot(stocks,'stocks',now=now),
        'sales':evaluate_source_snapshot(sales,'sales',now=now),
        'catalog':evaluate_source_snapshot(catalog,'catalog',now=now),
    }
    due=any(refresh_due(item,get_settings().sync_analytics_interval_seconds) for item in health.values())
    if not stocks or not sales:
        return None,None,catalog,[],_refresh(db,store),health
    stock_rows=list((stocks.payload or {}).get('rows') or [])
    sales_rows=list((sales.payload or {}).get('items') or [])
    sales_map={int(r['nm_id']):r for r in sales_rows if r.get('nm_id') is not None}
    facts=build_network_supply_inputs(stock_rows,sales_map)
    refresh=_refresh(db,store) if due else None
    return stocks,sales,catalog,facts,refresh,health


@router.get('/products')
def products(store_id:str|None=None,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    store=resolve_store(db,user,store_id); _connection(db,store.id)
    stocks,sales,catalog,facts,refresh,health=_facts(db,store)
    if not stocks or not sales:
        return {'store_id':store.id,'store_name':store.name,'marketplace':'wildberries','sync_required':True,'job_id':refresh.id if refresh else None,'freshness':None,'source_health':health,'products':[]}
    catalog_items=list((catalog.payload or {}).get('items') or []) if catalog else []
    catalog_by_nm={int(r['nm_id']):r for r in catalog_items if r.get('nm_id')}
    rows=[]
    seen=set()
    for fact in facts:
        nm_id=int(fact['nm_id']); seen.add(nm_id); card=catalog_by_nm.get(nm_id,{})
        rows.append({'nm_id':nm_id,'sku':card.get('vendor_code') or fact['sku'],'title':card.get('title') or fact.get('title') or f'WB товар {nm_id}','brand':card.get('brand') or '','subject_name':card.get('subject_name') or '','description':card.get('description') or '','photo_count':card.get('photo_count',0),'photos':card.get('photos') or [],'characteristics':card.get('characteristics') or [],'sizes':card.get('sizes') or [],'stock':fact['stock'],'orders_7d':fact['orders_period'],'avg_daily_orders':fact['avg_daily_sales'],'warehouse_count':len(fact.get('warehouse_stocks') or []),'warehouse_stocks':fact.get('warehouse_stocks') or [],'content_updated_at':card.get('updated_at')})
    for nm_id,card in catalog_by_nm.items():
        if nm_id in seen: continue
        rows.append({'nm_id':nm_id,'sku':card.get('vendor_code') or str(nm_id),'title':card.get('title') or f'WB товар {nm_id}','brand':card.get('brand') or '','subject_name':card.get('subject_name') or '','description':card.get('description') or '','photo_count':card.get('photo_count',0),'photos':card.get('photos') or [],'characteristics':card.get('characteristics') or [],'sizes':card.get('sizes') or [],'stock':0,'orders_7d':0,'avg_daily_orders':0,'warehouse_count':0,'warehouse_stocks':[],'content_updated_at':card.get('updated_at')})
    rows.sort(key=lambda r:(-r['orders_7d'],r['sku']))
    created=min(stocks.created_at,sales.created_at,*( [catalog.created_at] if catalog else [] ))
    age=max(item['age_seconds'] or 0 for item in health.values())
    return {'store_id':store.id,'store_name':store.name,'marketplace':'wildberries','catalog_live':bool(catalog),'sync_required':bool(refresh),'refresh_job_id':refresh.id if refresh else None,'freshness':{'created_at':created,'age_seconds':age},'source_health':health,'products':rows}


@router.get('/overview')
def overview(store_id:str|None=None,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    store=resolve_store(db,user,store_id); _connection(db,store.id)
    stocks,sales,catalog,facts,refresh,health=_facts(db,store)
    if not stocks or not sales:
        return {'store_id':store.id,'store_name':store.name,'marketplace':'wildberries','sync_required':True,'job_id':refresh.id if refresh else None,'freshness':None,'source_health':health,'kpis':None}
    total_stock=sum(max(0,int(r.get('stock') or 0)) for r in facts); orders_7d=sum(max(0,int(r.get('orders_period') or 0)) for r in facts); active=sum(1 for r in facts if r.get('avg_daily_sales',0)>0); low_stock=sum(1 for r in facts if r.get('avg_daily_sales',0)>0 and r.get('stock',0)<r.get('avg_daily_sales',0)*7)
    snapshots=[x for x in (stocks,sales,catalog) if x]; created=min(x.created_at for x in snapshots); age=max(item['age_seconds'] or 0 for item in health.values())
    return {'store_id':store.id,'store_name':store.name,'marketplace':'wildberries','sync_required':bool(refresh),'refresh_job_id':refresh.id if refresh else None,'freshness':{'created_at':created,'age_seconds':age},'source_health':health,'kpis':{'catalog_products':int((catalog.payload or {}).get('count',0)) if catalog else None,'products_with_history':len(facts),'active_products':active,'stock_units':total_stock,'orders_7d':orders_7d,'avg_orders_per_day':round(orders_7d/7,1),'low_stock_products':low_stock}}
