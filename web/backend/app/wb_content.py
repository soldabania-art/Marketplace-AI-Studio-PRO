"""Wildberries Content API product-card reader.

Uses the official /content/v2/get/cards/list endpoint with cursor pagination.
Only normalized seller-card facts are returned; marketplace tokens are never logged.
"""
import httpx

from .rate_limit import wait_marketplace_slot

WB_CARDS_LIST_URL='https://content-api.wildberries.ru/content/v2/get/cards/list'


def normalize_card(card:dict)->dict:
    photos=card.get('photos') or []
    sizes=card.get('sizes') or []
    skus=[]
    for size in sizes:
        for sku in (size.get('skus') or []):
            if sku: skus.append(str(sku))
    return {
        'nm_id':int(card.get('nmID') or 0),
        'vendor_code':str(card.get('vendorCode') or ''),
        'title':str(card.get('title') or ''),
        'brand':str(card.get('brand') or ''),
        'subject_id':card.get('subjectID'),
        'subject_name':str(card.get('subjectName') or ''),
        'description':str(card.get('description') or ''),
        'photos':photos,
        'photo_count':len(photos),
        'characteristics':card.get('characteristics') or [],
        'sizes':sizes,
        'skus':skus,
        'created_at':card.get('createdAt'),
        'updated_at':card.get('updatedAt'),
    }


async def fetch_wb_cards(token:str,max_pages:int=200)->list[dict]:
    cursor={ 'limit':100 }
    result=[]
    for _ in range(max_pages):
        await wait_marketplace_slot('wildberries',token,'content-cards-list',min_interval_seconds=0.6)
        body={'settings':{'sort':{'ascending':True},'filter':{'withPhoto':-1},'cursor':cursor}}
        async with httpx.AsyncClient(timeout=30.0) as client:
            response=await client.post(WB_CARDS_LIST_URL,json=body,headers={'Authorization':token})
        response.raise_for_status()
        payload=response.json() if response.content else {}
        cards=payload.get('cards') or []
        result.extend(normalize_card(card) for card in cards if card.get('nmID'))
        next_cursor=payload.get('cursor') or {}
        if len(cards)<100:
            break
        updated_at=next_cursor.get('updatedAt')
        nm_id=next_cursor.get('nmID')
        if not updated_at or not nm_id:
            break
        cursor={'limit':100,'updatedAt':updated_at,'nmID':nm_id}
    return result
