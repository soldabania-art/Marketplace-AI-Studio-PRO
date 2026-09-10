from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .billing_service import PLAN_CATALOG
from .config import get_settings
from .db import get_db
from .models import KnowledgeDocument, Membership, Subscription, SubscriptionStatus, User, Workspace
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
