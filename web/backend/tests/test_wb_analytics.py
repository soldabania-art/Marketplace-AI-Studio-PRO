from app.wb_analytics import build_network_supply_inputs, normalize_sales_history, normalize_stock_rows


def test_normalize_current_stock_rows():
    payload={'data':{'items':[{'nmId':10,'chrtId':20,'warehouseId':507,'warehouseName':'Коледино','regionName':'Центральный','quantity':43,'inWayToClient':14,'inWayFromClient':11}]}}
    rows=normalize_stock_rows(payload)
    assert rows==[{'nm_id':10,'chrt_id':20,'warehouse_id':507,'warehouse_name':'Коледино','region_name':'Центральный','quantity':43,'in_way_to_client':14,'in_way_from_client':11}]


def test_sales_velocity_uses_full_period_denominator():
    payload=[{'product':{'nmId':10,'vendorCode':'ART-10','title':'Товар'},'history':[{'date':'2026-09-01','orderCount':7,'buyoutCount':5},{'date':'2026-09-02','orderCount':0,'buyoutCount':0}]}]
    rows=normalize_sales_history(payload,7)
    assert rows[10]['orders']==7
    assert rows[10]['avg_daily_orders']==1.0
    assert rows[10]['vendor_code']=='ART-10'


def test_network_inputs_keep_warehouse_provenance_without_fake_allocation():
    stocks=[
        {'nm_id':10,'warehouse_id':1,'warehouse_name':'A','region_name':'R1','quantity':20,'chrt_id':1,'in_way_to_client':0,'in_way_from_client':0},
        {'nm_id':10,'warehouse_id':2,'warehouse_name':'B','region_name':'R2','quantity':30,'chrt_id':2,'in_way_to_client':0,'in_way_from_client':0},
    ]
    sales={10:{'nm_id':10,'vendor_code':'ART','title':'Товар','orders':14,'period_days':7,'avg_daily_orders':2.0}}
    rows=build_network_supply_inputs(stocks,sales)
    assert rows[0]['stock']==50
    assert rows[0]['avg_daily_sales']==2.0
    assert len(rows[0]['warehouse_stocks'])==2
