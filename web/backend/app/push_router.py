from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from .config import get_settings
from .db import get_db
from .models import User,PushSubscription,FboWatch
from .security import get_current_user
router=APIRouter()
class PushKeys(BaseModel): p256dh:str; auth:str
class PushBody(BaseModel): endpoint:str; keys:PushKeys
class WatchBody(BaseModel): marketplace:str='wildberries'; warehouse_filter:str=''; free_only:bool=True; enabled:bool=True
@router.get('/push/config')
def push_config(user:User=Depends(get_current_user)):
 settings=get_settings(); return {'enabled':bool(settings.vapid_public_key and settings.vapid_private_key and settings.vapid_subject),'public_key':settings.vapid_public_key}
@router.post('/push/subscriptions')
def save_push(body:PushBody,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
 row=db.query(PushSubscription).filter(PushSubscription.endpoint==body.endpoint).first()
 if row: row.user_id=user.id; row.p256dh=body.keys.p256dh; row.auth=body.keys.auth
 else: db.add(PushSubscription(user_id=user.id,endpoint=body.endpoint,p256dh=body.keys.p256dh,auth=body.keys.auth))
 db.commit(); return {'ok':True}
@router.post('/fbo/watch')
def save_watch(body:WatchBody,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
 if body.marketplace not in {'wildberries','ozon'}: raise HTTPException(400,'Unsupported marketplace')
 row=db.query(FboWatch).filter(FboWatch.user_id==user.id,FboWatch.marketplace==body.marketplace).first()
 if not row: row=FboWatch(user_id=user.id,marketplace=body.marketplace); db.add(row)
 row.warehouse_filter=body.warehouse_filter[:500]; row.free_only=body.free_only; row.enabled=body.enabled; db.commit(); return {'ok':True,'enabled':row.enabled,'watch_id':row.id}
