"""Wildberries Content API product-card reader and guarded writer.

Uses the official /content/v2/get/cards/list endpoint with cursor pagination.
Only normalized seller-card facts are returned; marketplace tokens are never logged.
"""
import httpx
from collections.abc import Callable

from .rate_limit import raise_for_marketplace_status, wait_marketplace_slot

WB_CARDS_LIST_URL='https://content-api.wildberries.ru/content/v2/get/cards/list'
WB_CARDS_UPDATE_URL='https://content-api.wildberries.ru/content/v2/cards/update'
WB_MEDIA_FILE_URL='https://content-api.wildberries.ru/content/v3/media/file'


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
        'dimensions':card.get('dimensions') or {},
        'photos':photos,
        'photo_count':len(photos),
        'characteristics':card.get('characteristics') or [],
        'sizes':sizes,
        'skus':skus,
        'created_at':card.get('createdAt'),
        'updated_at':card.get('updatedAt'),
    }


def build_card_update(card:dict,*,title:str,description:str)->dict:
    """Build the full WB update object while changing only approved copy fields."""
    result={
        'nmID':int(card.get('nm_id') or 0),
        'vendorCode':str(card.get('vendor_code') or ''),
        'brand':str(card.get('brand') or ''),
        'title':str(title).strip(),
        'description':str(description).strip(),
        'characteristics':[
            {'id':row.get('id'),'value':row.get('value')}
            for row in (card.get('characteristics') or [])
            if row.get('id') is not None
        ],
        'sizes':[
            {key:row.get(key) for key in ('chrtID','techSize','wbSize','skus') if row.get(key) is not None}
            for row in (card.get('sizes') or [])
        ],
    }
    if card.get('dimensions'):
        result['dimensions']=card['dimensions']
    if not result['nmID'] or not result['vendorCode']:
        raise ValueError('В карточке WB отсутствует nmID или артикул продавца.')
    if not 3<=len(result['title'])<=120:
        raise ValueError('Заголовок WB должен содержать от 3 до 120 символов.')
    if not 20<=len(result['description'])<=5000:
        raise ValueError('Описание WB должно содержать от 20 до 5000 символов.')
    return result


async def update_wb_card(token:str,payload:dict,*,before_send:Callable[[],None]|None=None)->dict:
    """Submit one complete card update to WB after the caller confirms it."""
    await wait_marketplace_slot('wildberries',token,'content-cards-update',min_interval_seconds=0.6)
    if before_send:
        before_send()
    async with httpx.AsyncClient(timeout=30.0) as client:
        response=await client.post(WB_CARDS_UPDATE_URL,json=[payload],headers={'Authorization':token})
    await raise_for_marketplace_status(response, 'wildberries', token, 'content-cards-update')
    if not response.content:
        return {'accepted':True,'status_code':response.status_code}
    try:
        body=response.json()
    except ValueError:
        body={'message':response.text[:1000]}
    return {'accepted':True,'status_code':response.status_code,'response':body}


async def upload_wb_media_file(token:str,*,nm_id:int,photo_number:int,raw:bytes,content_type:str,before_send:Callable[[],None]|None=None)->dict:
    """Append one explicitly approved image without replacing the existing media set."""
    await wait_marketplace_slot('wildberries',token,'content-media-file',min_interval_seconds=0.6)
    if before_send:
        before_send()
    headers={'Authorization':token,'X-Nm-Id':str(nm_id),'X-Photo-Number':str(photo_number)}
    files={'uploadfile':(f'trovendi-{nm_id}-{photo_number}.webp',raw,content_type)}
    async with httpx.AsyncClient(timeout=60.0) as client:
        response=await client.post(WB_MEDIA_FILE_URL,headers=headers,files=files)
    await raise_for_marketplace_status(response, 'wildberries', token, 'content-media-file')
    try:
        body=response.json() if response.content else {}
    except ValueError:
        body={'message':response.text[:1000]}
    if isinstance(body,dict) and body.get('error'):
        raise ValueError(str(body.get('errorText') or 'WB отклонил изображение.'))
    return {'accepted':True,'status_code':response.status_code,'response':body}


async def fetch_wb_card(token:str,*,nm_id:int,vendor_code:str)->dict|None:
    """Read one live card for the final optimistic-concurrency check."""
    await wait_marketplace_slot('wildberries',token,'content-card-read-before-write',min_interval_seconds=0.6)
    body={'settings':{'filter':{'withPhoto':-1,'textSearch':str(vendor_code)},'cursor':{'limit':100}}}
    async with httpx.AsyncClient(timeout=30.0) as client:
        response=await client.post(WB_CARDS_LIST_URL,json=body,headers={'Authorization':token})
    await raise_for_marketplace_status(response, 'wildberries', token, 'content-card-read-before-write')
    payload=response.json() if response.content else {}
    cards=[normalize_card(card) for card in (payload.get('cards') or []) if card.get('nmID')]
    return next((card for card in cards if card['nm_id']==int(nm_id)),None)


async def fetch_wb_cards(token:str,max_pages:int=200)->list[dict]:
    cursor={ 'limit':100 }
    result=[]
    for _ in range(max_pages):
        await wait_marketplace_slot('wildberries',token,'content-cards-list',min_interval_seconds=0.6)
        body={'settings':{'sort':{'ascending':True},'filter':{'withPhoto':-1},'cursor':cursor}}
        async with httpx.AsyncClient(timeout=30.0) as client:
            response=await client.post(WB_CARDS_LIST_URL,json=body,headers={'Authorization':token})
        await raise_for_marketplace_status(response, 'wildberries', token, 'content-cards-list')
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
