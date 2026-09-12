import asyncio

from app.wb_content import build_card_update, fetch_wb_card, normalize_card, update_wb_card, upload_wb_media_file


def test_normalize_card_keeps_real_content_fields():
    row=normalize_card({'nmID':123,'vendorCode':'SKU-1','title':'Товар','brand':'Brand','subjectID':42,'subjectName':'Органайзеры','description':'Описание','dimensions':{'length':10,'width':8,'height':4},'photos':[{'big':'x'}],'characteristics':[{'id':1,'name':'Цвет','value':['чёрный']}],'sizes':[{'skus':['460000000001']}],'updatedAt':'2026-09-07T10:00:00Z'})
    assert row['nm_id']==123
    assert row['vendor_code']=='SKU-1'
    assert row['brand']=='Brand'
    assert row['photo_count']==1
    assert row['skus']==['460000000001']
    assert row['characteristics'][0]['name']=='Цвет'
    assert row['dimensions']['length']==10


def test_card_update_changes_only_approved_copy_and_preserves_wb_fields():
    source=normalize_card({
        'nmID':123,
        'vendorCode':'SKU-1',
        'title':'Старое название',
        'brand':'Brand',
        'description':'Старое подробное описание товара',
        'dimensions':{'length':10,'width':8,'height':4},
        'characteristics':[{'id':1,'name':'Цвет','value':['чёрный']}],
        'sizes':[{'chrtID':77,'techSize':'0','wbSize':'','skus':['460000000001']}],
    })
    payload=build_card_update(source,title='Новое точное название',description='Новое подробное описание подтверждённого товара')
    assert payload['nmID']==123
    assert payload['title']=='Новое точное название'
    assert payload['description']=='Новое подробное описание подтверждённого товара'
    assert payload['brand']=='Brand'
    assert payload['dimensions']=={'length':10,'width':8,'height':4}
    assert payload['characteristics']==[{'id':1,'value':['чёрный']}]
    assert payload['sizes'][0]['chrtID']==77
    assert payload['sizes'][0]['skus']==['460000000001']


def test_wb_update_sends_one_complete_card_and_never_logs_token(monkeypatch):
    sent={}

    async def wait(*args,**kwargs):
        sent['wait']=(args,kwargs)

    class Response:
        content=b''
        status_code=200
        def raise_for_status(self): return None

    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self,*args): return None
        async def post(self,url,**kwargs):
            sent['url']=url
            sent['kwargs']=kwargs
            return Response()

    monkeypatch.setattr('app.wb_content.wait_marketplace_slot',wait)
    monkeypatch.setattr('app.wb_content.httpx.AsyncClient',lambda **kwargs:Client())
    result=asyncio.run(update_wb_card('secret-token',{'nmID':123,'vendorCode':'SKU-1'}))
    assert result=={'accepted':True,'status_code':200}
    assert sent['kwargs']['json']==[{'nmID':123,'vendorCode':'SKU-1'}]
    assert sent['kwargs']['headers']=={'Authorization':'secret-token'}
    assert sent['wait'][0][2]=='content-cards-update'


def test_card_dispatch_admission_runs_after_rate_limit_and_before_http(monkeypatch):
    order=[]

    async def wait(*args,**kwargs): order.append('rate-limit-complete')

    class Response:
        content=b''
        status_code=200
        def raise_for_status(self): return None

    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self,*args): return None
        async def post(self,*args,**kwargs): order.append('http-started'); return Response()

    monkeypatch.setattr('app.wb_content.wait_marketplace_slot',wait)
    monkeypatch.setattr('app.wb_content.httpx.AsyncClient',lambda **kwargs:Client())
    asyncio.run(update_wb_card('token',{'nmID':123},before_send=lambda:order.append('stop-admission')))
    assert order==['rate-limit-complete','stop-admission','http-started']


def test_live_preflight_reads_only_matching_vendor_card(monkeypatch):
    sent={}

    async def wait(*args,**kwargs): return None

    class Response:
        content=b'{}'
        def raise_for_status(self): return None
        def json(self): return {'cards':[{'nmID':41,'vendorCode':'SKU-1'},{'nmID':42,'vendorCode':'SKU-1','title':'Right'}]}

    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self,*args): return None
        async def post(self,url,**kwargs): sent.update(kwargs); return Response()

    monkeypatch.setattr('app.wb_content.wait_marketplace_slot',wait)
    monkeypatch.setattr('app.wb_content.httpx.AsyncClient',lambda **kwargs:Client())
    card=asyncio.run(fetch_wb_card('token',nm_id=42,vendor_code='SKU-1'))
    assert card['title']=='Right'
    assert sent['json']['settings']['filter']['textSearch']=='SKU-1'
    assert sent['json']['settings']['cursor']['limit']==100


def test_media_upload_appends_one_file_at_explicit_position(monkeypatch):
    sent={}

    async def wait(*args,**kwargs): sent['wait']=(args,kwargs)

    class Response:
        content=b'{"error":false}'
        status_code=200
        request=object()
        def raise_for_status(self): return None
        def json(self): return {'error':False}

    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self,*args): return None
        async def post(self,url,**kwargs): sent['url']=url; sent['kwargs']=kwargs; return Response()

    monkeypatch.setattr('app.wb_content.wait_marketplace_slot',wait)
    monkeypatch.setattr('app.wb_content.httpx.AsyncClient',lambda **kwargs:Client())
    result=asyncio.run(upload_wb_media_file('secret-token',nm_id=123,photo_number=4,raw=b'webp-bytes',content_type='image/webp'))
    assert result['accepted'] is True
    assert sent['url'].endswith('/content/v3/media/file')
    assert sent['kwargs']['headers']=={'Authorization':'secret-token','X-Nm-Id':'123','X-Photo-Number':'4'}
    assert sent['kwargs']['files']['uploadfile'][1:]==(b'webp-bytes','image/webp')
    assert sent['wait'][0][2]=='content-media-file'


def test_media_dispatch_admission_runs_after_rate_limit_and_before_http(monkeypatch):
    order=[]

    async def wait(*args,**kwargs): order.append('rate-limit-complete')

    class Response:
        content=b'{"error":false}'
        status_code=200
        def raise_for_status(self): return None
        def json(self): return {'error':False}

    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self,*args): return None
        async def post(self,*args,**kwargs): order.append('http-started'); return Response()

    monkeypatch.setattr('app.wb_content.wait_marketplace_slot',wait)
    monkeypatch.setattr('app.wb_content.httpx.AsyncClient',lambda **kwargs:Client())
    asyncio.run(upload_wb_media_file(
        'token',nm_id=123,photo_number=4,raw=b'webp',content_type='image/webp',
        before_send=lambda:order.append('stop-admission'),
    ))
    assert order==['rate-limit-complete','stop-admission','http-started']
