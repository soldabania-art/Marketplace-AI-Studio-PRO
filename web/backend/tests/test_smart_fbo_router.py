from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.smart_fbo_router import PlanRequest, SupplyRow, create_plan

class FakeDb:
    pass

def test_plan_uses_resolved_store(monkeypatch):
    store=SimpleNamespace(id='store-1',name='Мой магазин')
    monkeypatch.setattr('app.smart_fbo_router.resolve_store',lambda db,user,store_id: store)
    payload=PlanRequest(store_id='store-1',rows=[SupplyRow(sku='SKU-1',warehouse_id=10,warehouse_name='Коледино',stock=20,avg_daily_sales=5,acceptance_coefficient=0)])
    result=create_plan(payload,current_user=SimpleNamespace(id='u1'),db=FakeDb())
    assert result['store_id']=='store-1'
    assert result['summary']['recommended_units']==145
    assert result['summary']['ready_to_supply']==1
    assert result['live_marketplace_data'] is False

def test_plan_cannot_bypass_store_access(monkeypatch):
    def denied(db,user,store_id):
        raise HTTPException(status_code=403,detail='Нет доступа к магазину')
    monkeypatch.setattr('app.smart_fbo_router.resolve_store',denied)
    payload=PlanRequest(store_id='other-store',rows=[SupplyRow(sku='SKU-1',warehouse_name='A',stock=1,avg_daily_sales=1)])
    with pytest.raises(HTTPException) as exc:
        create_plan(payload,current_user=SimpleNamespace(id='u1'),db=FakeDb())
    assert exc.value.status_code==403
