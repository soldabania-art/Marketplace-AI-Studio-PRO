from types import SimpleNamespace

from app.profit_center_router import _public_amounts, _totals


def line(**values):
    defaults={
        'quantity':0,'gross_kopecks':0,'payout_kopecks':0,'commission_kopecks':0,
        'logistics_kopecks':0,'acquiring_kopecks':0,'storage_kopecks':0,
        'acceptance_kopecks':0,'penalty_kopecks':0,'deduction_kopecks':0,
        'additional_payment_kopecks':0,
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
