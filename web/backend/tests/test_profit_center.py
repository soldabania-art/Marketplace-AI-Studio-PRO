from types import SimpleNamespace
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from app.profit_center_router import ProductCostRequest, TaxProfileRequest, _financial_risks, _public_amounts, _public_import_summary, _sync_is_complete, _tax_kopecks, _totals, _validated_import_mapping, _verified_cost, save_tax_profile


def line(**values):
    defaults={
        'quantity':0,'gross_kopecks':0,'payout_kopecks':0,'commission_kopecks':0,
        'logistics_kopecks':0,'acquiring_kopecks':0,'storage_kopecks':0,
        'acceptance_kopecks':0,'penalty_kopecks':0,'deduction_kopecks':0,
        'additional_payment_kopecks':0,'operation':'','document_type':'',
        'source_line_id':'line','event_date':'','nm_id':None,'vendor_code':'',
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


def test_profit_never_marks_unknown_or_partial_import_as_complete():
    assert _sync_is_complete(True,{'complete':True,'schema_state':'valid','rejected_count':0}) is True
    assert _sync_is_complete(True,{'complete':True,'schema_state':'documented_empty','rejected_count':0}) is True
    assert _sync_is_complete(True,{'complete':True,'schema_state':'unknown','rejected_count':0}) is False
    assert _sync_is_complete(True,{'complete':True,'schema_state':'partial','rejected_count':1}) is False
    assert _sync_is_complete(False,{'complete':True,'schema_state':'valid','rejected_count':0}) is False


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


def test_verified_manufacturer_cost_is_exact_and_deterministic():
    payload=ProductCostRequest(
        store_id='store-1', operating_model='manufacturer', confirmed=True,
        components_rub={'materials':'520.45','direct_labor':'180','packaging':'49.55'},
        source_references={'materials':'Техкарта №7','direct_labor':'Наряд 18','packaging':'Спецификация упаковки'},
    )
    profile=SimpleNamespace(operating_model='manufacturer',status='confirmed')
    first=_verified_cost(payload,profile)
    second=_verified_cost(payload,profile)
    assert first[0]==75000
    assert first[2]=={'materials':52045,'direct_labor':18000,'packaging':4955}
    assert first[4]==second[4]
    assert len(first[4])==64


def test_verified_cost_requires_source_for_every_nonzero_component():
    payload=ProductCostRequest(
        store_id='store-1', operating_model='reseller', confirmed=True,
        components_rub={'purchase_price':'1000'}, source_references={},
    )
    with pytest.raises(HTTPException) as error:
        _verified_cost(payload,SimpleNamespace(operating_model='reseller',status='confirmed'))
    assert error.value.status_code==422
    assert 'источник' in error.value.detail.lower()


def test_cost_model_must_match_confirmed_store_profile():
    payload=ProductCostRequest(
        store_id='store-1', operating_model='manufacturer', confirmed=True,
        components_rub={'materials':'100'}, source_references={'materials':'Техкарта'},
    )
    with pytest.raises(HTTPException) as error:
        _verified_cost(payload,SimpleNamespace(operating_model='reseller',status='confirmed'))
    assert error.value.status_code==422


def test_mixed_store_can_select_concrete_cost_model_per_sku():
    payload=ProductCostRequest(
        store_id='store-1', operating_model='distributor', confirmed=True,
        components_rub={'net_purchase':'999.99'}, source_references={'net_purchase':'УПД поставщика'},
    )
    total,model,_,_,_=_verified_cost(payload,SimpleNamespace(operating_model='mixed',status='confirmed'))
    assert total==99999
    assert model=='distributor'


def test_legacy_confirmed_total_remains_supported():
    payload=ProductCostRequest(store_id='store-1',cogs_rub='123.45',confirmed=True)
    total,model,components,sources,_=_verified_cost(payload,None)
    assert (total,model,components,sources)==(12345,'legacy_total',{'legacy_total':12345},{})


def test_import_mapping_is_allowlisted_and_normalized():
    assert _validated_import_mapping({'nm_id':' Артикул WB ','components':{'materials':' Сырьё '}})=={
        'nm_id':'Артикул WB','operating_model':'','row_source':'','components':{'materials':'Сырьё'},
    }


def test_import_mapping_rejects_unknown_component():
    with pytest.raises(HTTPException) as error:
        _validated_import_mapping({'nm_id':'nmId','components':{'password':'Секрет'}})
    assert error.value.status_code==422


def test_import_history_expires_preview_without_exposing_rows():
    now=datetime(2026,9,10,tzinfo=timezone.utc)
    result=_public_import_summary(SimpleNamespace(id='batch',source_system='1c',source_document_reference='doc',
        payload_sha256='a'*64,status='preview',rows=[{'nm_id':1,'cogs_kopecks':99999}],
        created_at=now-timedelta(days=2),expires_at=now-timedelta(seconds=1),committed_at=None),now)
    assert result['status']=='expired'
    assert result['row_count']==1
    assert 'rows' not in result


def test_financial_risks_exclude_advertising_and_source_payload():
    rows=[line(source_line_id='penalty-1',penalty_kopecks=2500,event_date='2026-09-09T10:00:00',operation='Штраф',document_type='Продажа',nm_id=7,vendor_code='SKU-7',source_payload={'secret':'never expose'}),
          line(source_line_id='ads-1',deduction_kopecks=9900,operation='Услуги WB Продвижение'),
          line(source_line_id='deduction-1',deduction_kopecks=1200,event_date='2026-09-08',operation='Удержание')]
    result=_financial_risks(rows)
    assert result['event_count']==2
    assert result['penalty_total']=='25.00'
    assert result['deduction_total']=='12.00'
    assert result['items'][0]['source_line_id']=='penalty-1'
    assert all('source_payload' not in item for item in result['items'])
    assert result['categories']==[
        {'kind':'penalty','label':'Штраф','count':1,'amount':'25.00'},
        {'kind':'deduction','label':'Удержание','count':1,'amount':'12.00'},
    ]
