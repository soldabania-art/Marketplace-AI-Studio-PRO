from datetime import datetime, timezone
from types import SimpleNamespace

from app.seller_data_router import overview, products

class Query:
    def __init__(self,row): self.row=row
    def filter(self,*args): return self
    def first(self): return self.row
class Db:
    def __init__(self,connection): self.connection=connection
    def query(self,*args): return Query(self.connection)

def _snapshots(now):
    stock=SimpleNamespace(created_at=now,payload={'rows':[{'nm_id':1,'warehouse_id':10,'warehouse_name':'A','quantity':5},{'nm_id':2,'warehouse_id':20,'warehouse_name':'B','quantity':100}]})
    sales=SimpleNamespace(created_at=now,payload={'items':[{'nm_id':1,'vendor_code':'SKU1','title':'One','orders':14,'period_days':7,'avg_daily_orders':2},{'nm_id':2,'vendor_code':'SKU2','title':'Two','orders':7,'period_days':7,'avg_daily_orders':1}]})
    return stock,sales

def test_products_are_store_scoped_snapshot_data(monkeypatch):
    store=SimpleNamespace(id='s1',name='Store',workspace_id='w1'); now=datetime.now(timezone.utc); stock,sales=_snapshots(now)
    monkeypatch.setattr('app.seller_data_router.resolve_store',lambda db,user,store_id:store)
    monkeypatch.setattr('app.seller_data_router.latest_snapshot',lambda db,store_id,marketplace,snapshot_type: stock if snapshot_type=='stocks' else sales)
    result=products(store_id='s1',user=SimpleNamespace(id='u1'),db=Db(SimpleNamespace(enabled=True)))
    assert result['products'][0]['sku']=='SKU1'
    assert result['products'][0]['stock']==5
    assert result['products'][0]['orders_7d']==14

def test_overview_uses_only_supported_snapshot_kpis(monkeypatch):
    store=SimpleNamespace(id='s1',name='Store',workspace_id='w1'); now=datetime.now(timezone.utc); stock,sales=_snapshots(now)
    monkeypatch.setattr('app.seller_data_router.resolve_store',lambda db,user,store_id:store)
    monkeypatch.setattr('app.seller_data_router.latest_snapshot',lambda db,store_id,marketplace,snapshot_type: stock if snapshot_type=='stocks' else sales)
    result=overview(store_id='s1',user=SimpleNamespace(id='u1'),db=Db(SimpleNamespace(enabled=True)))
    assert result['kpis']['orders_7d']==21
    assert result['kpis']['stock_units']==105
    assert 'revenue' not in result['kpis']
