"""Read-only Wildberries promotion statistics for Profit Center."""
import hashlib
import json
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

import httpx

from .rate_limit import wait_marketplace_slot
from .marketplace_page import MarketplacePageResult

WB_CAMPAIGN_COUNT_URL='https://advert-api.wildberries.ru/adv/v1/promotion/count'
WB_FULL_STATS_URL='https://advert-api.wildberries.ru/adv/v3/fullstats'
SCHEMA_SOURCE_URL='https://dev.wildberries.ru/docs/openapi/promotion'


def _int(value) -> int:
    if value is None or value == '': return 0
    try: parsed=Decimal(str(value).replace(',','.'))
    except (InvalidOperation,TypeError,ValueError) as exc: raise ValueError('invalid integer') from exc
    if not parsed.is_finite() or parsed != parsed.to_integral_value(): raise ValueError('invalid integer')
    return int(parsed)


def _kopecks(value) -> int:
    if value is None or value == '': return 0
    try: parsed=Decimal(str(value).replace(',','.'))
    except (InvalidOperation,TypeError,ValueError) as exc: raise ValueError('invalid money') from exc
    if not parsed.is_finite(): raise ValueError('non-finite money')
    return int((parsed*100).quantize(Decimal('1'),rounding=ROUND_HALF_UP))


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
    if not isinstance(payload,dict) or not isinstance(payload.get('adverts'),list):
        raise ValueError('unknown campaign count schema')
    found=set()
    for group in payload['adverts']:
        if not isinstance(group,dict) or not isinstance(group.get('advert_list'),list):
            raise ValueError('invalid campaign group')
        for item in group['advert_list']:
            if not isinstance(item,dict): raise ValueError('invalid campaign row')
            campaign_id=_int(item.get('advertId'))
            if campaign_id<=0: raise ValueError('missing advertId')
            found.add(campaign_id)
    return sorted(found)


def _campaigns(payload) -> list[dict]:
    if isinstance(payload,list): return [item for item in payload if isinstance(item,dict)]
    if isinstance(payload,dict):
        value=payload.get('data')
        if isinstance(value,list): return [item for item in value if isinstance(item,dict)]
    return []


def _normalize_advertising_stats(payload) -> list[dict]:
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


def parse_advertising_stats_page(payload) -> MarketplacePageResult:
    if not isinstance(payload,list):
        return MarketplacePageResult([],0,0,0,None,'unknown',[{'code':'unknown_schema','expected':'JSON array','actual':type(payload).__name__}])
    if not payload:
        return MarketplacePageResult([],0,0,0,None,'documented_empty')
    items=[]; evidence=[]; accepted_campaigns=0
    for index,campaign in enumerate(payload):
        try:
            if not isinstance(campaign,dict): raise ValueError('campaign must be an object')
            if _int(campaign.get('advertId'))<=0: raise ValueError('missing advertId')
            if not isinstance(campaign.get('days'),list): raise ValueError('days must be an array')
            for day_index,day in enumerate(campaign['days']):
                if not isinstance(day,dict): raise ValueError('day must be an object')
                event_date=str(day.get('date') or '')
                if len(event_date)<10: raise ValueError('missing day date')
                if not isinstance(day.get('apps'),list): raise ValueError('apps must be an array')
                for app_index,app in enumerate(day['apps']):
                    if not isinstance(app,dict): raise ValueError('app must be an object')
                    field='nm' if 'nm' in app else 'nms'
                    rows=app.get(field,[])
                    if not isinstance(rows,(list,dict)): raise ValueError('nm must be an array or object')
                    nested_rows=[rows] if isinstance(rows,dict) else rows
                    for row_index,source in enumerate(nested_rows):
                        path=f'days[{day_index}].apps[{app_index}].{field}[{row_index}]'
                        if not isinstance(source,dict): raise ValueError(f'{path} must be an object')
                        if _int(source.get('nmId') or source.get('nm_id'))<=0:
                            raise ValueError(f'{path}.nmId is required')
            normalized=_normalize_advertising_stats([campaign])
            items.extend(normalized); accepted_campaigns+=1
        except (ValueError,InvalidOperation) as exc:
            evidence.append({'code':'rejected_campaign','row':index,'reason':str(exc)[:200]})
    rejected=len(payload)-accepted_campaigns
    return MarketplacePageResult(items,len(payload),len(items),rejected,None,'partial' if rejected else 'valid',evidence)


def normalize_advertising_stats(payload) -> list[dict]:
    page=parse_advertising_stats_page(payload)
    if not page.safe_to_apply: raise ValueError(f'advertising schema is {page.schema_state}')
    return page.items


async def fetch_campaign_ids(token: str) -> MarketplacePageResult:
    await wait_marketplace_slot('wildberries',token,'promotion-read',min_interval_seconds=20.0)
    async with httpx.AsyncClient(timeout=60.0) as client:
        response=await client.get(WB_CAMPAIGN_COUNT_URL,headers={'Authorization':token})
    response.raise_for_status()
    payload=response.json() if response.content else None
    try:
        ids=campaign_ids(payload)
    except ValueError as exc:
        return MarketplacePageResult([],0,0,0,None,'unknown',[{'code':'campaign_schema_error','reason':str(exc)}])
    state='documented_empty' if not ids else 'valid'
    return MarketplacePageResult([{'campaign_id':value} for value in ids],len(ids),len(ids),0,None,state)


async def fetch_advertising_stats(token: str,*,ids:list[int],date_from:str,date_to:str) -> MarketplacePageResult:
    if not ids or len(ids)>50: raise ValueError('ids must contain from 1 to 50 campaigns')
    if len(date_chunks(date_from,date_to))!=1: raise ValueError('advertising period must not exceed 31 days')
    await wait_marketplace_slot('wildberries',token,'promotion-read',min_interval_seconds=20.0)
    params={'ids':','.join(str(value) for value in ids),'beginDate':date_from,'endDate':date_to}
    async with httpx.AsyncClient(timeout=90.0) as client:
        response=await client.get(WB_FULL_STATS_URL,params=params,headers={'Authorization':token})
    response.raise_for_status()
    return parse_advertising_stats_page(response.json() if response.content else None)
