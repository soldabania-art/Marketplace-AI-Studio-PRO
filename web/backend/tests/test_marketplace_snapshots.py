from datetime import datetime, timezone
from types import SimpleNamespace

from app.smart_fbo_router import snapshot_plan

class Query:
    def __init__(self,row): self.row=row
    def filter(self,*args): return self
    def first(self): return self.row
class Db:
    def __init__(self,connection): self.connection=connection
    def query(self,*args): return Query(self.connection)

def test_snapshot_plan_queues_sync_when_snapshots_missing(monkeypatch):
    store=SimpleNamespace(id='s1',name='Store',workspace_id='w1')
    monkeypatch.setattr('app.smart_fbo_router.resolve_store',lambda db,user,store_id:store)
    monkeypatch.setattr('app.smart_fbo_router.latest_snapshot',lambda *a,**k:None)
    monkeypatch.setattr('app.smart_fbo_router._queue_refresh',lambda db,store:SimpleNamespace(id='job1'))
    result=snapshot_plan(store_id='s1',current_user=SimpleNamespace(id='u1'),db=Db(SimpleNamespace(enabled=True)))
    assert result['mode']=='snapshot_pending'
    assert result['sync_required'] is True
    assert result['job_id']=='job1'

def test_snapshot_plan_uses_persisted_facts_without_marketplace_call(monkeypatch):
    store=SimpleNamespace(id='s1',name='Store',workspace_id='w1')
    now=datetime.now(timezone.utc)
    stock=SimpleNamespace(id='st1',created_at=now,payload={'rows':[{'nm_id':1,'warehouse_id':10,'warehouse_name':'A','quantity':5}]})
    sales=SimpleNamespace(id='sa1',created_at=now,payload={'items':[{'nm_id':1,'vendor_code':'SKU','title':'Item','orders':14,'period_days':7,'avg_daily_orders':2}]})
    monkeypatch.setattr('app.smart_fbo_router.resolve_store',lambda db,user,store_id:store)
    monkeypatch.setattr('app.smart_fbo_router.latest_snapshot',lambda db,store_id,marketplace,snapshot_type: stock if snapshot_type=='stocks' else sales)
    result=snapshot_plan(store_id='s1',current_user=SimpleNamespace(id='u1'),db=Db(SimpleNamespace(enabled=True)))
    assert result['mode']=='deterministic_snapshot_v1'
    assert result['summary']['products_with_sales_history']==1
    assert result['recommendations'][0]['sku']=='SKU'
    assert result['sources']['stock_snapshot_id']=='st1'
