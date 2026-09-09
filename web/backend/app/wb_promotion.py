"""Read-only Wildberries promotion statistics for Profit Center."""
import hashlib
import json
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

import httpx

from .rate_limit import wait_marketplace_slot

WB_CAMPAIGN_COUNT_URL='https://advert-api.wildberries.ru/adv/v1/promotion/count'
WB_FULL_STATS_URL='https://advert-api.wildberries.ru/adv/v3/fullstats'


def _int(value) -> int:
    try: return int(Decimal(str(value or 0).replace(',','.')))
    except (InvalidOperation,TypeError,ValueError): return 0


def _kopecks(value) -> int:
    try: return int((Decimal(str(value or 0).replace(',','.'))*100).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
    except (InvalidOperation,TypeError,ValueError): return 0


def date_chunks(date_from: str,date_to: str,max_days: int=31) -> list[tuple[str,str]]:
    start=date.fromisoformat(date_from); end=date.fromisoformat(date_to)
    if end<start: raise ValueError('date_to must not be before date_from')
    chunks=[]
    while start<=end:
        chunk_end=min(end,start+timedelta(days=max(1,max_days)-1))
        chunks.append((start.isoformat(),chunk_end.isoformat()))
        start=chunk_end+timedelta(days=1)
    return chunks


def campaign_ids(payload) -> list[int]:
    found=set()
    def walk(value):
        if isinstance(value,list):
            for item in value: walk(item)
        elif isinstance(value,dict):
            for key in ('advertId','advert_id'):
                campaign_id=_int(value.get(key))
                if campaign_id>0: found.add(campaign_id)
            for key,item in value.items():
                if key not in {'advertId','advert_id'}: walk(item)
    walk(payload)
    return sorted(found)


def _campaigns(payload) -> list[dict]:
    if isinstance(payload,list): return [item for item in payload if isinstance(item,dict)]
    if isinstance(payload,dict):
        value=payload.get('data')
        if isinstance(value,list): return [item for item in value if isinstance(item,dict)]
    return []


def normalize_advertising_stats(payload) -> list[dict]:
    grouped=defaultdict(lambda:{'spend_kopecks':0,'attributed_revenue_kopecks':0,'views':0,'clicks':0,'orders':0,'units':0,'source_rows':[],'campaign_name':''})
    for campaign in _campaigns(payload):
        campaign_id=_int(campaign.get('advertId') or campaign.get('advert_id') or campaign.get('id'))
        if campaign_id<=0: continue
        campaign_name=str(campaign.get('name') or campaign.get('advertName') or '')
        for day in campaign.get('days') or []:
            if not isinstance(day,dict): continue
            event_date=str(day.get('date') or '')[:10]
            if not event_date: continue
            found_nm=False
            for app in day.get('apps') or []:
                if not isinstance(app,dict): continue
                rows=app.get('nm') or app.get('nms') or []
                if isinstance(rows,dict): rows=[rows]
                for source in rows:
                    if not isinstance(source,dict): continue
                    nm_id=_int(source.get('nmId') or source.get('nm_id')) or None
                    found_nm=True
                    key=(campaign_id,event_date,nm_id)
                    target=grouped[key]; target['campaign_name']=campaign_name
                    target['spend_kopecks']+=_kopecks(source.get('sum'))
                    target['attributed_revenue_kopecks']+=_kopecks(source.get('sumPrice') if source.get('sumPrice') is not None else source.get('sum_price'))
                    for field,aliases in {'views':('views',),'clicks':('clicks',),'orders':('orders',),'units':('shks','units')}.items():
                        target[field]+=_int(next((source.get(alias) for alias in aliases if source.get(alias) is not None),0))
                    target['source_rows'].append(source)
            if not found_nm:
                key=(campaign_id,event_date,None); target=grouped[key]; target['campaign_name']=campaign_name
                target['spend_kopecks']+=_kopecks(day.get('sum'))
                target['attributed_revenue_kopecks']+=_kopecks(day.get('sumPrice') if day.get('sumPrice') is not None else day.get('sum_price'))
                for field,aliases in {'views':('views',),'clicks':('clicks',),'orders':('orders',),'units':('shks','units')}.items():
                    target[field]+=_int(next((day.get(alias) for alias in aliases if day.get(alias) is not None),0))
                target['source_rows'].append(day)
    result=[]
    for (campaign_id,event_date,nm_id),values in grouped.items():
        source={'campaign_id':campaign_id,'event_date':event_date,'nm_id':nm_id,'rows':values.pop('source_rows')}
        encoded=json.dumps(source,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
        result.append({
            'source_line_id':f'{campaign_id}:{event_date}:{nm_id or 0}',
            'campaign_id':campaign_id,'campaign_name':values.pop('campaign_name'),'nm_id':nm_id,'event_date':event_date,
            **values,'source_sha256':hashlib.sha256(encoded).hexdigest(),'source_payload':source,
        })
    return sorted(result,key=lambda item:(item['event_date'],item['campaign_id'],item['nm_id'] or 0))


async def fetch_campaign_ids(token: str) -> list[int]:
    await wait_marketplace_slot('wildberries',token,'promotion-read',min_interval_seconds=20.0)
    async with httpx.AsyncClient(timeout=60.0) as client:
        response=await client.get(WB_CAMPAIGN_COUNT_URL,headers={'Authorization':token})
    response.raise_for_status()
    return campaign_ids(response.json() if response.content else {})


async def fetch_advertising_stats(token: str,*,ids:list[int],date_from:str,date_to:str) -> list[dict]:
    if not ids or len(ids)>50: raise ValueError('ids must contain from 1 to 50 campaigns')
    if len(date_chunks(date_from,date_to))!=1: raise ValueError('advertising period must not exceed 31 days')
    await wait_marketplace_slot('wildberries',token,'promotion-read',min_interval_seconds=20.0)
    params={'ids':','.join(str(value) for value in ids),'beginDate':date_from,'endDate':date_to}
    async with httpx.AsyncClient(timeout=90.0) as client:
        response=await client.get(WB_FULL_STATS_URL,params=params,headers={'Authorization':token})
    response.raise_for_status()
    return normalize_advertising_stats(response.json() if response.content else [])
