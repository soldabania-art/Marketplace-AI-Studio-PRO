from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.profit_center_router import TaxProfileRequest, _public_amounts, _tax_kopecks, _totals, save_tax_profile


def line(**values):
    defaults={
        'quantity':0,'gross_kopecks':0,'payout_kopecks':0,'commission_kopecks':0,
        'logistics_kopecks':0,'acquiring_kopecks':0,'storage_kopecks':0,
        'acceptance_kopecks':0,'penalty_kopecks':0,'deduction_kopecks':0,
        'additional_payment_kopecks':0,'operation':'','document_type':'',
    }
    return SimpleNamespace(**(defaults|values))


def test_profit_totals_are_deterministic_and_do_not_call_ai():
    totals=_totals([
        line(quantity=2,gross_kopecks=100000,payout_kopecks=70000,commission_kopecks=20000,logistics_kopecks=5000,acquiring_kopecks=1000),
        line(quantity=-1,gross_kopecks=-50000,payout_kopecks=-35000,logistics_kopecks=2500,penalty_kopecks=300,additional_payment_kopecks=800),
    ])
    assert totals['net_units']==1
    assert totals['wb_net_kopecks']==27000
    assert _public_amounts(totals)['wb_net']=='270.00'


def test_missing_money_is_zero_not_invented():
    totals=_totals([line(quantity=3)])
    assert totals['wb_net_kopecks']==0
    assert _public_amounts(totals)['gross']=='0.00'


def test_advertising_deduction_is_exposed_for_double_charge_reconciliation():
    totals=_totals([line(deduction_kopecks=1250,operation='Услуги WB Продвижение')])
    assert totals['deduction_kopecks']==1250
    assert totals['advertising_deduction_kopecks']==1250
    assert totals['wb_net_kopecks']==-1250


def test_tax_reserve_uses_only_confirmed_basis_and_integer_kopecks():
    totals=_totals([line(gross_kopecks=100001,payout_kopecks=70000)])
    assert _tax_kopecks(totals,None) is None
    assert _tax_kopecks(totals,SimpleNamespace(basis='gross_sales',rate_bps=600))==6000
    assert _tax_kopecks(totals,SimpleNamespace(basis='wb_payout',rate_bps=600))==4200


def test_tax_profile_cannot_be_saved_without_explicit_confirmation():
    payload=TaxProfileRequest(store_id='store-1',basis='gross_sales',rate_percent='6',confirmed=False)
    with pytest.raises(HTTPException) as error:
        save_tax_profile(payload,user=SimpleNamespace(id='user-1'),db=None)
    assert error.value.status_code==422
