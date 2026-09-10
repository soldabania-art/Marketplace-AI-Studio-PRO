from __future__ import annotations
from datetime import datetime,timezone
import hashlib,hmac,re,uuid
from typing import Literal
from fastapi import APIRouter,Depends,Header,HTTPException,Request
from pydantic import BaseModel,Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from .db import get_db
from .config import get_settings
from .models import FulfillmentPartner,User,VaultDocument,VaultDocumentEvent
from .security import get_current_user
from .store_access import resolve_store

router=APIRouter(prefix='/document-vault',tags=['document-vault'])
ALLOWED_TYPES={'application/pdf','image/jpeg','image/png','application/json','application/xml','text/xml','text/csv'}

class AuthorizeUpload(BaseModel):
    store_id:str=Field(min_length=1,max_length=36);display_name:str=Field(min_length=1,max_length=240);content_type:str=Field(min_length=3,max_length=120);byte_size:int=Field(gt=0,le=25_000_000);subject_type:Literal['seller','buyer','order','fulfillment','accounting'];document_type:Literal['contract','act','invoice','receipt','upd','waybill','return','claim','fiscal_receipt','other'];fulfillment_partner_id:str|None=None;external_reference:str=Field(default='',max_length=240)
class FinalizeUpload(BaseModel):
    content_sha256:str=Field(pattern=r'^[a-f0-9]{64}$');byte_size:int=Field(gt=0,le=25_000_000)
class ScanResult(BaseModel):
    document_id:str=Field(min_length=1,max_length=36);content_sha256:str=Field(pattern=r'^[a-f0-9]{64}$');verdict:Literal['clean','infected','error'];scanner:str=Field(min_length=1,max_length=80)

def _public(row):return {'id':row.id,'subject_type':row.subject_type,'document_type':row.document_type,'display_name':row.display_name,'content_type':row.content_type,'byte_size':row.byte_size,'status':row.status,'scan_status':row.scan_status,'retention_class':row.retention_class,'retention_until':row.retention_until,'legal_hold':row.legal_hold,'fulfillment_partner_id':row.fulfillment_partner_id,'created_at':row.created_at,'finalized_at':row.finalized_at,'download_available':row.status=='available' and row.scan_status=='clean'}

@router.post('/uploads/authorize',status_code=201)
def authorize_upload(payload:AuthorizeUpload,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    store=resolve_store(db,user,payload.store_id)
    if payload.content_type not in ALLOWED_TYPES:raise HTTPException(422,'Разрешены PDF, JPEG, PNG, JSON, XML и CSV. Архивы и исполняемые файлы запрещены.')
    if payload.fulfillment_partner_id and db.get(FulfillmentPartner,payload.fulfillment_partner_id) is None:raise HTTPException(404,'Fulfillment partner not found')
    name=re.sub(r'[\\/\x00-\x1f]+',' ',payload.display_name).strip()[:240]
    reference_hash=hashlib.sha256(payload.external_reference.strip().encode()).hexdigest() if payload.external_reference.strip() else ''
    row=VaultDocument(workspace_id=store.workspace_id,store_id=store.id,fulfillment_partner_id=payload.fulfillment_partner_id,uploaded_by_user_id=user.id,subject_type=payload.subject_type,document_type=payload.document_type,display_name=name,external_reference_sha256=reference_hash,storage_path=f'vault/{store.workspace_id}/{store.id}/{uuid.uuid4()}',content_type=payload.content_type,byte_size=payload.byte_size,status='upload_pending',scan_status='pending');db.add(row);db.flush();db.add(VaultDocumentEvent(document_id=row.id,workspace_id=store.workspace_id,store_id=store.id,actor_user_id=user.id,event_type='upload.authorized',payload={'content_type':payload.content_type,'byte_size':payload.byte_size}));db.commit();db.refresh(row)
    return {'document':_public(row),'storage_path':row.storage_path,'max_bytes':25_000_000,'private_storage_required':True}

@router.post('/documents/{document_id}/finalize')
def finalize_upload(document_id:str,payload:FinalizeUpload,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    row=db.get(VaultDocument,document_id)
    if row is None:raise HTTPException(404,'Document not found')
    resolve_store(db,user,row.store_id)
    if row.uploaded_by_user_id!=user.id:raise HTTPException(403,'Завершить загрузку может только её автор')
    if row.status!='upload_pending':raise HTTPException(409,'Загрузка уже завершена или отменена')
    if row.byte_size!=payload.byte_size:raise HTTPException(409,'Размер файла изменился после авторизации')
    row.content_sha256=payload.content_sha256;row.status='quarantined';row.scan_status='pending';row.finalized_at=datetime.now(timezone.utc);db.add(VaultDocumentEvent(document_id=row.id,workspace_id=row.workspace_id,store_id=row.store_id,actor_user_id=user.id,event_type='upload.finalized',payload={'sha256':payload.content_sha256,'byte_size':payload.byte_size,'scan_status':'pending'}));db.commit();return {'document':_public(row),'notice':'Документ сохранён в закрытом хранилище и помещён в карантин до проверки безопасности.'}

@router.post('/scan-results')
async def scan_result(request:Request,x_document_scan_signature:str=Header(default=''),db:Session=Depends(get_db)):
    secret=get_settings().document_scan_webhook_secret
    if not secret:raise HTTPException(503,'Document scanner is not configured')
    raw=await request.body();expected='sha256='+hmac.new(secret.encode(),raw,hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected,x_document_scan_signature):raise HTTPException(401,'Invalid scan signature')
    try:payload=ScanResult.model_validate_json(raw)
    except Exception as exc:raise HTTPException(422,'Invalid scan result') from exc
    row=db.get(VaultDocument,payload.document_id)
    if row is None:raise HTTPException(404,'Document not found')
    if row.content_sha256!=payload.content_sha256:raise HTTPException(409,'Document digest mismatch')
    if row.scan_status!='pending':raise HTTPException(409,'Scan result already recorded')
    row.scan_status=payload.verdict;row.status='available' if payload.verdict=='clean' else 'blocked' if payload.verdict=='infected' else 'quarantined'
    db.add(VaultDocumentEvent(document_id=row.id,workspace_id=row.workspace_id,store_id=row.store_id,actor_user_id=row.uploaded_by_user_id,event_type='scan.completed',payload={'scanner':payload.scanner,'verdict':payload.verdict,'sha256':payload.content_sha256}));db.commit()
    return {'accepted':True,'document':_public(row)}

@router.get('/documents/{document_id}/download-authorize')
def authorize_download(document_id:str,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    row=db.get(VaultDocument,document_id)
    if row is None:raise HTTPException(404,'Document not found')
    resolve_store(db,user,row.store_id)
    if row.status!='available' or row.scan_status!='clean':raise HTTPException(423,'Документ недоступен до успешной проверки безопасности')
    db.add(VaultDocumentEvent(document_id=row.id,workspace_id=row.workspace_id,store_id=row.store_id,actor_user_id=user.id,event_type='download.authorized',payload={'sha256':row.content_sha256}));db.commit()
    return {'storage_path':row.storage_path,'display_name':row.display_name,'content_type':row.content_type,'byte_size':row.byte_size,'content_sha256':row.content_sha256}

@router.get('/documents')
def documents(store_id:str,user:User=Depends(get_current_user),db:Session=Depends(get_db)):
    store=resolve_store(db,user,store_id);rows=db.scalars(select(VaultDocument).where(VaultDocument.store_id==store.id).order_by(VaultDocument.created_at.desc()).limit(200)).all();return {'items':[_public(row) for row in rows],'storage':'private_object_storage','card_data_allowed':False,'max_items':200}
