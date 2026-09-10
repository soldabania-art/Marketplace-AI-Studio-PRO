from datetime import datetime, timezone
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .billing_service import PLAN_CATALOG
from .config import get_settings
from .db import get_db
from .fulfillment_adapters import assert_capabilities
from .models import FulfillmentFacility, FulfillmentPartner, KnowledgeDocument, Membership, Subscription, SubscriptionStatus, User, Workspace
from .security import require_platform_admin, require_platform_admin_step_up
from .support_service import document_checksum

router = APIRouter()
VALID_PLANS = set(PLAN_CATALOG)

class KnowledgeDraftRequest(BaseModel):
    slug: str = Field(pattern=r'^[a-z0-9][a-z0-9-]{1,118}$')
    version: int = Field(ge=1, le=100000)
    title: str = Field(min_length=3, max_length=240)
    body: str = Field(min_length=20, max_length=30000)
    source_url: str = Field(default='', max_length=500)
    product_version: str = Field(default='', max_length=40)
    expires_at: datetime | None = None

class FulfillmentPartnerRequest(BaseModel):
    code: str = Field(pattern=r'^[a-z0-9][a-z0-9_-]{1,62}$')
    name: str = Field(min_length=2,max_length=160)
    countries: list[str] = Field(min_length=1,max_length=20)
    integration_mode: Literal['api','webhook','sftp','csv'] = 'api'
    capabilities: list[str] = Field(default_factory=list,max_length=20)
    documentation_url: str = Field(default='',max_length=500)

class FulfillmentFacilityRequest(BaseModel):
    external_id: str = Field(min_length=1,max_length=120)
    name: str = Field(min_length=2,max_length=200)
    country_code: str = Field(pattern=r'^[A-Z]{2}$')
    city: str = Field(default='',max_length=120)
    timezone_name: str = Field(default='UTC',max_length=64)
    service_modes: list[Literal['fbo','fbs','dbs','cross_dock','returns']] = Field(default_factory=list,max_length=5)
    marketplace_codes: list[str] = Field(default_factory=list,max_length=20)

@router.get('/admin/knowledge')
def knowledge_documents(_: User = Depends(require_platform_admin), db: Session = Depends(get_db)):
    rows=db.scalars(select(KnowledgeDocument).order_by(KnowledgeDocument.slug,KnowledgeDocument.version.desc()).limit(200)).all()
    return {'items':[{'id':r.id,'slug':r.slug,'version':r.version,'title':r.title,'status':r.status,'source_url':r.source_url or None,'product_version':r.product_version,'reviewed_at':r.reviewed_at,'expires_at':r.expires_at} for r in rows]}

@router.post('/admin/knowledge',status_code=status.HTTP_201_CREATED)
def create_knowledge_draft(payload: KnowledgeDraftRequest, _: User = Depends(require_platform_admin_step_up), db: Session = Depends(get_db)):
    row=KnowledgeDocument(slug=payload.slug,version=payload.version,title=payload.title.strip(),body=payload.body.strip(),source_url=payload.source_url.strip(),product_version=payload.product_version.strip(),expires_at=payload.expires_at,checksum_sha256=document_checksum(title=payload.title,body=payload.body,source_url=payload.source_url,version=payload.version));db.add(row)
    try:db.commit()
    except Exception as exc:db.rollback();raise HTTPException(409,'Документ с такой версией уже существует') from exc
    db.refresh(row);return {'id':row.id,'status':row.status,'checksum_sha256':row.checksum_sha256}

@router.post('/admin/knowledge/{document_id}/approve')
def approve_knowledge_document(document_id: str, admin: User = Depends(require_platform_admin_step_up), db: Session = Depends(get_db)):
    row=db.get(KnowledgeDocument,document_id)
    if row is None:raise HTTPException(404,'Knowledge document not found')
    now=datetime.now(timezone.utc)
    if row.expires_at is not None and row.expires_at<=now:raise HTTPException(422,'Нельзя одобрить уже истёкший документ')
    row.status='approved';row.reviewed_by_user_id=admin.id;row.reviewed_at=now;row.effective_at=now;db.commit();return {'id':row.id,'status':row.status,'reviewed_at':row.reviewed_at,'checksum_sha256':row.checksum_sha256}

@router.get('/admin/fulfillment/partners')
def fulfillment_partners(_:User=Depends(require_platform_admin),db:Session=Depends(get_db)):
    rows=db.scalars(select(FulfillmentPartner).order_by(FulfillmentPartner.name).limit(500)).all()
    return {'items':[{'id':r.id,'code':r.code,'name':r.name,'countries':r.countries,'integration_mode':r.integration_mode,'capabilities':r.capabilities,'status':r.status,'documentation_url':r.documentation_url or None,'security_reviewed_at':r.security_reviewed_at} for r in rows]}

@router.post('/admin/fulfillment/partners',status_code=status.HTTP_201_CREATED)
def create_fulfillment_partner(payload:FulfillmentPartnerRequest,_:User=Depends(require_platform_admin_step_up),db:Session=Depends(get_db)):
    countries=sorted(set(payload.countries))
    if any(len(code)!=2 or not code.isupper() for code in countries):raise HTTPException(422,'Страны задаются кодами ISO 3166-1 alpha-2')
    try:capabilities=assert_capabilities(payload.capabilities)
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc
    row=FulfillmentPartner(code=payload.code,name=payload.name.strip(),countries=countries,integration_mode=payload.integration_mode,capabilities=capabilities,documentation_url=payload.documentation_url.strip(),status='discovery');db.add(row)
    try:db.commit()
    except Exception as exc:db.rollback();raise HTTPException(409,'Партнёр с таким кодом уже существует') from exc
    db.refresh(row);return {'id':row.id,'code':row.code,'status':row.status}

@router.post('/admin/fulfillment/partners/{partner_id}/facilities',status_code=status.HTTP_201_CREATED)
def create_fulfillment_facility(partner_id:str,payload:FulfillmentFacilityRequest,_:User=Depends(require_platform_admin_step_up),db:Session=Depends(get_db)):
    partner=db.get(FulfillmentPartner,partner_id)
    if partner is None:raise HTTPException(404,'Fulfillment partner not found')
    if payload.country_code not in partner.countries:raise HTTPException(422,'Страна склада отсутствует в географии партнёра')
    row=FulfillmentFacility(partner_id=partner.id,external_id=payload.external_id.strip(),name=payload.name.strip(),country_code=payload.country_code,city=payload.city.strip(),timezone_name=payload.timezone_name.strip(),service_modes=sorted(set(payload.service_modes)),marketplace_codes=sorted(set(payload.marketplace_codes)));db.add(row)
    try:db.commit()
    except Exception as exc:db.rollback();raise HTTPException(409,'Склад с таким внешним ID уже существует у партнёра') from exc
    db.refresh(row);return {'id':row.id,'partner_id':partner.id,'active':row.active}

@router.post('/admin/fulfillment/partners/{partner_id}/verify')
def verify_fulfillment_partner(partner_id:str,admin:User=Depends(require_platform_admin_step_up),db:Session=Depends(get_db)):
    partner=db.get(FulfillmentPartner,partner_id)
    if partner is None:raise HTTPException(404,'Fulfillment partner not found')
    facility=db.scalar(select(FulfillmentFacility).where(FulfillmentFacility.partner_id==partner.id,FulfillmentFacility.active.is_(True)))
    if not partner.documentation_url or not partner.capabilities or facility is None:raise HTTPException(422,'Для пилота нужны документация, разрешённые возможности и хотя бы один активный склад')
    partner.status='pilot';partner.security_reviewed_at=datetime.now(timezone.utc);db.commit()
    return {'id':partner.id,'status':partner.status,'security_reviewed_at':partner.security_reviewed_at,'reviewed_by':admin.id}


def _latest_subscription(db: Session, workspace_id: str) -> Subscription | None:
    return db.scalar(
        select(Subscription)
        .where(Subscription.workspace_id == workspace_id)
        .order_by(Subscription.created_at.desc())
    )


@router.get("/admin/summary")
def summary(_: User = Depends(require_platform_admin), db: Session = Depends(get_db)):
    users = db.scalar(select(func.count()).select_from(User)) or 0
    active_users = db.scalar(select(func.count()).select_from(User).where(User.is_active.is_(True))) or 0
    workspaces = db.scalar(select(func.count()).select_from(Workspace)) or 0
    active_subscriptions = db.scalar(
        select(func.count()).select_from(Subscription).where(Subscription.status == SubscriptionStatus.active)
    ) or 0
    trial_subscriptions = db.scalar(
        select(func.count()).select_from(Subscription).where(Subscription.status == SubscriptionStatus.trial)
    ) or 0
    return {
        "users": users,
        "active_users": active_users,
        "workspaces": workspaces,
        "active_subscriptions": active_subscriptions,
        "trial_subscriptions": trial_subscriptions,
        "billing_provider": get_settings().billing_provider,
    }


@router.get("/admin/users")
def users(_: User = Depends(require_platform_admin), db: Session = Depends(get_db)):
    rows = db.scalars(select(User).order_by(User.created_at.desc()).limit(200)).all()
    result = []
    for user in rows:
        membership = db.scalar(select(Membership).where(Membership.user_id == user.id))
        workspace = db.get(Workspace, membership.workspace_id) if membership else None
        subscription = _latest_subscription(db, membership.workspace_id) if membership else None
        result.append({
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "is_active": user.is_active,
            "email_verified": user.email_verified,
            "created_at": user.created_at,
            "workspace_id": workspace.id if workspace else None,
            "workspace_name": workspace.name if workspace else None,
            "role": membership.role.value if membership else None,
            "plan_code": subscription.plan_code if subscription else "none",
            "subscription_status": subscription.status.value if subscription else "none",
        })
    return {"items": result, "limit": 200}


@router.patch("/admin/users/{user_id}/status")
def set_user_status(user_id: str, active: bool, admin: User = Depends(require_platform_admin_step_up), db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.id == admin.id and not active:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Administrator cannot disable own account")
    user.is_active = active
    db.commit()
    return {"id": user.id, "is_active": user.is_active}


@router.patch("/admin/workspaces/{workspace_id}/plan")
def set_workspace_plan(workspace_id: str, plan_code: str, _: User = Depends(require_platform_admin_step_up), db: Session = Depends(get_db)):
    if plan_code not in VALID_PLANS:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unknown plan")
    workspace = db.get(Workspace, workspace_id)
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    subscription = _latest_subscription(db, workspace_id)
    target_status = SubscriptionStatus.trial if plan_code == "trial" else SubscriptionStatus.active
    if subscription is None:
        subscription = Subscription(workspace_id=workspace_id, plan_code=plan_code, status=target_status, provider="admin_override")
        db.add(subscription)
    else:
        subscription.plan_code = plan_code
        subscription.status = target_status
        subscription.provider = subscription.provider or "admin_override"
    subscription.current_period_started_at = None
    subscription.current_period_expires_at = None
    subscription.cancel_at_period_end = False
    subscription.canceled_at = None
    db.commit()
    return {"workspace_id": workspace_id, "plan_code": plan_code, "status": target_status.value}
