import asyncio
import json
from pathlib import Path

import pytest

from app.wb_finance import fetch_financial_report_page, normalize_financial_row, parse_financial_report_page

FIXTURES=Path(__file__).with_name('fixtures')


def test_normalize_financial_row_keeps_source_and_exact_kopecks():
    source={
        'rrdId':987654321,
        'realizationReportId':42,
        'nmId':123,
        'vendorCode':'SKU-1',
        'subjectName':'Органайзер',
        'docTypeName':'Продажа',
        'saleDate':'2026-09-08T14:10:00Z',
        'quantity':2,
        'retailAmount':'1234.56',
        'ppvzForPay':'900,10',
        'ppvzSalesCommission':'200.00',
        'deliveryRub':'50.25',
        'rebillLogisticCost':'1.25',
        'acquiringFee':'12.11',
        'storageFee':'3.50',
        'acceptance':'4',
        'penalty':'5.05',
        'deduction':'6.06',
        'additionalPayment':'7.07',
    }
    row=normalize_financial_row(source)
    assert row['source_line_id']=='987654321'
    assert row['event_date']=='2026-09-08T14:10:00Z'
    assert row['gross_kopecks']==123456
    assert row['payout_kopecks']==90010
    assert row['logistics_kopecks']==5150
    assert row['acquiring_kopecks']==1211
    assert row['source_payload']==source
    assert len(row['source_sha256'])==64


def test_return_quantity_is_negative_and_report_date_is_fallback():
    row=normalize_financial_row({'rrd_id':'12','doc_type_name':'Возврат','quantity':'2','reportDate':'2026-09-07'})
    assert row['quantity']==-2
    assert row['event_date']=='2026-09-07'


def test_finance_reader_posts_cursor_and_handles_current_response(monkeypatch):
    sent={}

    async def wait(*args,**kwargs): sent['wait']=(args,kwargs)

    class Response:
        status_code=200
        content=b'{}'
        def raise_for_status(self): return None
        def json(self): return [{'rrdId':77,'nmId':5,'forPay':'10.50','reportDate':'2026-09-09'}]

    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self,*args): return None
        async def post(self,url,**kwargs): sent['url']=url; sent['kwargs']=kwargs; return Response()

    monkeypatch.setattr('app.wb_finance.wait_marketplace_slot',wait)
    monkeypatch.setattr('app.wb_finance.httpx.AsyncClient',lambda **kwargs:Client())
    page=asyncio.run(fetch_financial_report_page('secret',date_from='2026-09-01',date_to='2026-09-09',rrd_id=11))
    assert page.items[0]['source_line_id']=='77'
    assert page.items[0]['payout_kopecks']==1050
    assert (page.raw_count,page.accepted_count,page.rejected_count,page.cursor,page.schema_state)==(1,1,0,77,'valid')
    assert sent['kwargs']['json']=={'dateFrom':'2026-09-01','dateTo':'2026-09-09','rrdId':11}
    assert sent['kwargs']['headers']=={'Authorization':'secret'}
    assert sent['wait'][0][2]=='finance-sales-report'
    assert sent['wait'][1]['min_interval_seconds']==60.0


def test_finance_partial_page_rejects_malformed_money_missing_cursor_and_non_finite():
    payload=json.loads((FIXTURES/'wb_finance_partial_invalid.json').read_text())
    page=parse_financial_report_page(payload)
    assert page.schema_state=='partial'
    assert (page.raw_count,page.accepted_count,page.rejected_count)==(3,1,2)
    assert page.safe_to_apply is False
    assert page.cursor==1001
    assert {item['code'] for item in page.evidence}=={'rejected_row'}
    with pytest.raises(ValueError): normalize_financial_row({'rrdId':1,'forPay':'Infinity'})


def test_finance_unknown_http_200_schema_is_not_empty_or_complete():
    page=parse_financial_report_page({'data':[]},status_code=200)
    assert page.schema_state=='unknown'
    assert page.safe_to_apply is False
    assert page.evidence[0]['code']=='unknown_schema'


def test_finance_documented_204_is_the_only_complete_empty_page():
    page=parse_financial_report_page(None,status_code=204)
    assert page.schema_state=='documented_empty'
    assert page.safe_to_apply is True
    assert page.items==[]
