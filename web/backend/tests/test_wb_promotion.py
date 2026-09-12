import asyncio
import hashlib
import json
import uuid
from pathlib import Path

import pytest

from app.marketplace_page import MarketplacePageResult
from app.marketplace_sync import sync_wb_advertising
from app.db import Base, SessionLocal, engine
from app.models import MarketplaceAdvertisingLine, MarketplaceConnection, MarketplaceSnapshot, Membership, MembershipRole, Store, User, Workspace
from app.wb_promotion import campaign_ids, date_chunks, fetch_advertising_stats, normalize_advertising_stats, parse_advertising_stats_page

FIXTURES=Path(__file__).with_name('fixtures')
Base.metadata.create_all(bind=engine)


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
    page=asyncio.run(fetch_advertising_stats('secret',ids=[12,34],date_from='2026-09-01',date_to='2026-09-09'))
    assert page.items==[]
    assert page.schema_state=='documented_empty'
    assert sent['url'].endswith('/adv/v3/fullstats')
    assert sent['kwargs']['params']=={'ids':'12,34','beginDate':'2026-09-01','endDate':'2026-09-09'}
    assert sent['kwargs']['headers']=={'Authorization':'secret'}
    assert sent['wait'][0][2]=='promotion-read'
    assert sent['wait'][1]['min_interval_seconds']==20.0


def test_advertising_unknown_schema_and_non_finite_money_are_rejected():
    unknown=json.loads((FIXTURES/'wb_advertising_unknown_schema.json').read_text())
    assert parse_advertising_stats_page(unknown).schema_state=='unknown'
    malformed=json.loads((FIXTURES/'wb_advertising_valid_page.json').read_text())
    malformed[0]['days'][0]['apps'][0]['nm'][0]['sum']='NaN'
    page=parse_advertising_stats_page(malformed)
    assert page.schema_state=='partial'
    assert page.rejected_count==1
    assert page.safe_to_apply is False


@pytest.mark.parametrize('nested_rows',[None,[None],[{'nmId':123,'sum':'10.00'},None]])
def test_advertising_rejects_every_malformed_nested_nm_row(nested_rows):
    payload=[{'advertId':77,'name':'Поиск','days':[{'date':'2026-09-08','apps':[{'nm':nested_rows}]}]}]
    page=parse_advertising_stats_page(payload)
    assert page.schema_state=='partial'
    assert page.rejected_count==1
    assert page.safe_to_apply is False
    assert page.evidence
    assert 'nm' in page.evidence[0]['reason']


def test_documented_empty_advertising_page_is_safe_and_distinct_from_corruption():
    page=parse_advertising_stats_page([])
    assert page.schema_state=='documented_empty'
    assert page.safe_to_apply is True
    assert page.items==[]


def test_corrupt_nested_advertising_page_preserves_saved_rows_and_checksum(monkeypatch):
    suffix=uuid.uuid4().hex
    with SessionLocal() as db:
        user=User(email=f'ads-{suffix}@example.com',password_hash='test')
        workspace=Workspace(name=f'Advertising {suffix}')
        db.add_all([user,workspace]);db.flush()
        db.add(Membership(user_id=user.id,workspace_id=workspace.id,role=MembershipRole.owner))
        store=Store(workspace_id=workspace.id,name=f'Store {suffix}')
        db.add(store);db.flush()
        db.add(MarketplaceConnection(user_id=user.id,store_id=store.id,marketplace='wildberries',encrypted_token='encrypted-test',enabled=True))
        original_payload={'campaign_id':77,'event_date':'2026-09-08','nm_id':123,'rows':[{'nmId':123,'sum':'15.00'}]}
        original_checksum=hashlib.sha256(json.dumps(original_payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        db.add(MarketplaceAdvertisingLine(
            store_id=store.id,marketplace='wildberries',source_line_id='77:2026-09-08:123',campaign_id=77,
            campaign_name='Existing',nm_id=123,event_date='2026-09-08',spend_kopecks=1500,
            attributed_revenue_kopecks=5000,views=20,clicks=4,orders=2,units=2,
            source_sha256=original_checksum,source_payload=original_payload,
        ))
        db.commit();store_id=store.id

    corrupt=[{'advertId':77,'name':'Поиск','days':[{'date':'2026-09-08','apps':[{'nm':[{'nmId':123,'sum':'10.00'},None]}]}]}]
    async def corrupt_page(*args,**kwargs): return parse_advertising_stats_page(corrupt)
    monkeypatch.setattr('app.marketplace_sync.decrypt_connection',lambda value:'token')
    monkeypatch.setattr('app.marketplace_sync.fetch_advertising_stats',corrupt_page)

    with pytest.raises(RuntimeError,match='advertising page rejected'):
        asyncio.run(sync_wb_advertising({'store_id':store_id,'date_from':'2026-09-08','date_to':'2026-09-08','campaign_ids':[77]}))

    with SessionLocal() as db:
        saved=db.query(MarketplaceAdvertisingLine).filter(MarketplaceAdvertisingLine.store_id==store_id).one()
        assert saved.source_sha256==original_checksum
        assert saved.spend_kopecks==1500
        assert saved.source_payload==original_payload
        snapshot=db.query(MarketplaceSnapshot).filter(
            MarketplaceSnapshot.store_id==store_id,
            MarketplaceSnapshot.snapshot_type=='advertising_sync',
        ).order_by(MarketplaceSnapshot.created_at.desc()).first()
        assert snapshot.payload['complete'] is False
        assert snapshot.payload['schema_state']=='partial'
        assert snapshot.payload['rejected_count']==1
        assert snapshot.payload['evidence']
        assert 'nm' in snapshot.payload['evidence'][0]['reason']


def test_invalid_advertising_page_never_deletes_previous_rows(monkeypatch):
    deleted=[]; snapshots=[]
    connection=object(); store=type('Store',(),{'id':'s1','workspace_id':'w1'})()
    class Query:
        def filter(self,*args): return self
        def first(self): return connection
    class Db:
        def query(self,model): return Query()
        def get(self,model,key): return store
        def delete(self,row): deleted.append(row)
        def close(self): pass
    async def bad_page(*args,**kwargs):
        return MarketplacePageResult([],0,0,0,None,'unknown',[{'code':'unknown_schema'}])
    monkeypatch.setattr('app.marketplace_sync.SessionLocal',lambda:Db())
    monkeypatch.setattr('app.marketplace_sync.decrypt_connection',lambda value:'token')
    monkeypatch.setattr('app.marketplace_sync.fetch_advertising_stats',bad_page)
    monkeypatch.setattr('app.marketplace_sync.save_snapshot',lambda db,**kwargs:snapshots.append(kwargs))
    with pytest.raises(RuntimeError):
        asyncio.run(sync_wb_advertising({'store_id':'s1','date_from':'2026-09-01','date_to':'2026-09-09','campaign_ids':[77]}))
    assert deleted==[]
    assert snapshots[0]['payload']['complete'] is False
    assert snapshots[0]['payload']['schema_state']=='unknown'
