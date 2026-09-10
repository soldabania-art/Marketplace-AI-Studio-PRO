from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from .db import get_db
from .fulfillment_adapters import assert_capabilities
from .models import FulfillmentConnection, FulfillmentPartner, User
from .security import get_current_user, require_step_up_session
from .store_access import require_store_admin, resolve_store

router=APIRouter(prefix='/fulfillment',tags=['fulfillment'])

@router.get('/partners')
def partners(store_id:str,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    store=resolve_store(db,user,store_id)
    linked={row.partner_id:row for row in db.scalars(select(FulfillmentConnection).where(FulfillmentConnection.store_id==store.id)).all()}
    rows=db.scalars(select(FulfillmentPartner).order_by(FulfillmentPartner.name).limit(500)).all()
    return {'store_id':store.id,'items':[{'id':row.id,'code':row.code,'name':row.name,'countries':row.countries,'integration_mode':row.integration_mode,'capabilities':row.capabilities,'status':row.status,'documentation_url':row.documentation_url or None,'security_reviewed':bool(row.security_reviewed_at),'connection':({'id':linked[row.id].id,'status':linked[row.id].status,'enabled_capabilities':linked[row.id].enabled_capabilities,'verified_at':linked[row.id].verified_at} if row.id in linked else None)} for row in rows]}

@router.post('/partners/{partner_id}/connections')
def plan_connection(partner_id:str,store_id:str,user:User=Depends(get_current_user),_:object=Depends(require_step_up_session),db:Session=Depends(get_db)):
    store=resolve_store(db,user,store_id);require_store_admin(db,user,store)
    partner=db.get(FulfillmentPartner,partner_id)
    if partner is None:raise HTTPException(404,'Fulfillment partner not found')
    if partner.status not in {'verified','pilot'} or partner.security_reviewed_at is None:raise HTTPException(409,'Партнёр ещё не прошёл проверку интеграции и безопасности')
    row=db.scalar(select(FulfillmentConnection).where(FulfillmentConnection.store_id==store.id,FulfillmentConnection.partner_id==partner.id))
    if row is None:row=FulfillmentConnection(workspace_id=store.workspace_id,store_id=store.id,partner_id=partner.id,status='planned',enabled_capabilities=assert_capabilities(partner.capabilities));db.add(row);db.commit();db.refresh(row)
    return {'id':row.id,'status':row.status,'partner_code':partner.code,'enabled_capabilities':row.enabled_capabilities,'notice':'Подключение запланировано. Учетные данные и живой обмен появятся только через защищённый адаптер партнёра.'}
