import asyncio

from app.wb_promotion import campaign_ids, date_chunks, fetch_advertising_stats, normalize_advertising_stats


def test_date_chunks_cover_ninety_days_without_overlap():
    chunks=date_chunks('2026-06-12','2026-09-09')
    assert chunks==[('2026-06-12','2026-07-12'),('2026-07-13','2026-08-12'),('2026-08-13','2026-09-09')]


def test_campaign_ids_reads_nested_count_response_and_deduplicates():
    payload={'adverts':[{'type':9,'status':9,'advert_list':[{'advertId':30},{'advertId':20}]},{'advert_list':[{'advertId':30}]}]}
    assert campaign_ids(payload)==[20,30]


def test_advertising_rows_aggregate_apps_by_campaign_day_and_product():
    payload=[{'advertId':77,'name':'Поиск','days':[{'date':'2026-09-08','apps':[
        {'nm':[{'nmId':123,'sum':10.25,'sumPrice':100,'views':10,'clicks':2,'orders':1,'shks':1}]},
        {'nm':[{'nm_id':123,'sum':'2,25','sum_price':'20.50','views':5,'clicks':1,'orders':0,'shks':0}]},
    ]}]}]
    rows=normalize_advertising_stats(payload)
    assert len(rows)==1
    assert rows[0]['source_line_id']=='77:2026-09-08:123'
    assert rows[0]['spend_kopecks']==1250
    assert rows[0]['attributed_revenue_kopecks']==12050
    assert rows[0]['views']==15
    assert rows[0]['clicks']==3
    assert rows[0]['source_payload']['campaign_id']==77


def test_fullstats_uses_current_get_parameters_and_rate_limit(monkeypatch):
    sent={}
    async def wait(*args,**kwargs): sent['wait']=(args,kwargs)
    class Response:
        content=b'[]'
        def raise_for_status(self): return None
        def json(self): return []
    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self,*args): return None
        async def get(self,url,**kwargs): sent['url']=url; sent['kwargs']=kwargs; return Response()
    monkeypatch.setattr('app.wb_promotion.wait_marketplace_slot',wait)
    monkeypatch.setattr('app.wb_promotion.httpx.AsyncClient',lambda **kwargs:Client())
    rows=asyncio.run(fetch_advertising_stats('secret',ids=[12,34],date_from='2026-09-01',date_to='2026-09-09'))
    assert rows==[]
    assert sent['url'].endswith('/adv/v3/fullstats')
    assert sent['kwargs']['params']=={'ids':'12,34','beginDate':'2026-09-01','endDate':'2026-09-09'}
    assert sent['kwargs']['headers']=={'Authorization':'secret'}
    assert sent['wait'][0][2]=='promotion-read'
    assert sent['wait'][1]['min_interval_seconds']==20.0
