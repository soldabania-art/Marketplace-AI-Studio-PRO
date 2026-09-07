import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .db import get_db
from .fbo_service import fetch_wb_slots
from .marketplace_connections import decrypt_connection
from .models import MarketplaceConnection, User
from .security import get_current_user

api_router = APIRouter()

DEMO_META = {"mode":"demo","live_data":False,"message":"Marketplace connection is not active. Values are demonstration data only."}

@api_router.get('/dashboard')
def dashboard(): return {'meta':DEMO_META,'kpis':{'revenue':482640,'net_profit':127430,'ad_spend':41280,'orders':327,'currency':'RUB'}}

@api_router.get('/profit')
def profit(): return {'meta':DEMO_META,'period_days':30,'net_profit':1846320,'margin_percent':26.4,'ad_ratio_percent':9.1,'formula':'payout - cogs - sku_ad_spend'}

@api_router.get('/director')
def director(): return {'meta':DEMO_META,'items':[{'id':'demo-loss-sku','severity':'critical','title':'SKU 18374629 уходит в убыток','estimated_effect_rub_month':9800,'action':'review_advertising','external_write':False},{'id':'demo-seo','severity':'warning','title':'У 6 карточек просело SEO','estimated_effect':'+11–18% traffic','action':'regenerate_seo','external_write':False}]}

@api_router.get('/integrations/status')
def integration_status(): return {'meta':DEMO_META,'wildberries':{'connected':False,'status':'not_configured'},'ozon':{'connected':False,'status':'not_configured'}}

@api_router.get('/marketplaces/commission')
def marketplace_commission(marketplace:str=Query(pattern='^(wildberries|ozon)$'),sku:str='',current_user:User=Depends(get_current_user)):
    raise HTTPException(status_code=409,detail=f'{marketplace}: магазин или тарифная интеграция ещё не подключены. Комиссия не подставлена.')

@api_router.get('/fbo/slots')
async def fbo_slots(
    marketplace:str=Query(default='wildberries',pattern='^(wildberries|ozon)$'),
    free_only:bool=False,
    current_user:User=Depends(get_current_user),
    db:Session=Depends(get_db),
):
    if marketplace == 'ozon':
        raise HTTPException(status_code=409,detail='Ozon FBO: интеграция слотов приёмки ещё не подключена.')

    connection=(
        db.query(MarketplaceConnection)
        .filter(
            MarketplaceConnection.user_id==current_user.id,
            MarketplaceConnection.marketplace=='wildberries',
            MarketplaceConnection.enabled.is_(True),
        )
        .first()
    )
    if not connection:
        raise HTTPException(status_code=409,detail='Wildberries FBW: сначала подключите магазин в настройках.')

    token=decrypt_connection(connection)
    try:
        slots=await fetch_wb_slots(token)
    except httpx.HTTPStatusError as exc:
        status=exc.response.status_code if exc.response is not None else 502
        if status in {401,403}:
            raise HTTPException(status_code=409,detail='Wildberries отклонил токен магазина. Переподключите WB.')
        if status == 429:
            raise HTTPException(status_code=429,detail='Wildberries временно ограничил частоту запросов. Повторите позже.')
        raise HTTPException(status_code=502,detail='Wildberries временно недоступен. Повторите позже.')
    except httpx.RequestError:
        raise HTTPException(status_code=502,detail='Не удалось связаться с Wildberries. Повторите позже.')

    if free_only:
        slots=[slot for slot in slots if slot.get('free_acceptance')]
    return {
        'marketplace':'wildberries',
        'live_data':True,
        'coefficients':[0] if free_only else [0,1],
        'scope':'all_warehouses',
        'count':len(slots),
        'slots':slots,
    }
