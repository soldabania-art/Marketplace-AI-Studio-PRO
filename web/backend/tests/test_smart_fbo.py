from app.smart_fbo import SupplyInput,recommend_supply,recommend_many

def test_supply_math_and_provenance():
    row=recommend_supply(SupplyInput(sku='A',warehouse_id=1,warehouse_name='Коледино',stock=20,avg_daily_sales=5,lead_time_days=7,target_cover_days=21,safety_days=5,acceptance_coefficient=0))
    assert row['reorder_point']==60
    assert row['target_stock']==165
    assert row['recommended_qty']==145
    assert row['days_of_cover']==4.0
    assert row['urgency']=='critical'
    assert row['acceptance_available'] is True
    assert row['provenance']['method']=='deterministic_v1'

def test_zero_sales_does_not_invent_supply():
    row=recommend_supply(SupplyInput(sku='B',warehouse_id=2,warehouse_name='Тула',stock=30,avg_daily_sales=0))
    assert row['recommended_qty']==0
    assert row['days_of_cover'] is None
    assert row['urgency']=='no_sales'

def test_critical_items_are_ranked_first():
    rows=recommend_many([
        SupplyInput(sku='OK',warehouse_id=1,warehouse_name='A',stock=500,avg_daily_sales=2),
        SupplyInput(sku='LOW',warehouse_id=2,warehouse_name='B',stock=1,avg_daily_sales=10),
    ])
    assert rows[0]['sku']=='LOW'
