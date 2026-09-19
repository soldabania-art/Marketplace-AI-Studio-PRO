from datetime import datetime, timedelta, timezone
import hashlib
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session

from .billing_service import PLAN_CATALOG
from .config import get_settings
from .db import get_db
from .fulfillment_adapters import assert_capabilities
from .models import BackgroundJob, FulfillmentFacility, FulfillmentPartner, JobStatus, KnowledgeDocument, MarketplaceConnection, Membership, PlatformStaffRole, SecurityEvent, Store, Subscription, SubscriptionStatus, User, Workspace
from .platform_access import grant_project_manager, require_effective_owner_after_lock, revoke_platform_role, serialized_platform_access, set_user_active_serialized
from .security import require_platform_admin, require_platform_admin_step_up, require_platform_summary
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

class PlatformGrantRequest(BaseModel):
    user_id: str = Field(min_length=36,max_length=36)
    role: Literal['project_manager']

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
    return db.scalar(select(Subscription).where(Subscription.workspace_id == workspace_id).order_by(Subscription.created_at.desc()))


def _job_public(row: BackgroundJob) -> dict:
    return {
        'id': row.id,
        'workspace_id': row.workspace_id,
        'store_id': row.store_id,
        'job_type': row.job_type,
        'status': row.status.value,
        'priority': row.priority,
        'attempts': row.attempts,
        'max_attempts': row.max_attempts,
        'available_at': row.available_at,
        'locked_at': row.locked_at,
        'heartbeat_at': getattr(row, 'heartbeat_at', None),
        'locked_by': row.locked_by or None,
        'attempt_id': getattr(row, 'attempt_id', '') or None,
        'last_error': (row.last_error or '')[:1000],
        'created_at': row.created_at,
        'updated_at': row.updated_at,
        'finished_at': row.finished_at,
        'payload_keys': sorted((row.payload or {}).keys()),
    }


@router.get('/admin/jobs')
def background_jobs(job_status: JobStatus | None = Query(default=None, alias='status'), _: User = Depends(require_platform_admin), db: Session = Depends(get_db)):
    query = select(BackgroundJob)
    if job_status is not None:
        query = query.where(BackgroundJob.status == job_status)
    rows = list(db.scalars(query.order_by(BackgroundJob.created_at.desc()).limit(200)).all())
    counts = {value.value: (db.scalar(select(func.count()).select_from(BackgroundJob).where(BackgroundJob.status == value)) or 0) for value in JobStatus}
    lease_seconds = max(30, get_settings().job_lease_seconds)
    stale_before = datetime.now(timezone.utc) - timedelta(seconds=lease_seconds)
    stale_running = db.scalar(select(func.count()).select_from(BackgroundJob).where(
        BackgroundJob.status == JobStatus.running,
        func.coalesce(BackgroundJob.heartbeat_at, BackgroundJob.locked_at) < stale_before,
    )) or 0
    oldest_ready = db.scalar(select(func.min(BackgroundJob.created_at)).where(BackgroundJob.status.in_([JobStatus.queued, JobStatus.retry])))
    return {'items': [_job_public(row) for row in rows], 'counts': counts, 'stale_running': stale_running, 'oldest_ready_at': oldest_ready, 'limit': 200}


@router.post('/admin/jobs/{job_id}/requeue')
def requeue_background_job(job_id: str, admin: User = Depends(require_platform_admin_step_up), db: Session = Depends(get_db)):
    row = db.get(BackgroundJob, job_id)
    if row is None:
        raise HTTPException(404, 'Background job not found')
    if row.status not in {JobStatus.dead, JobStatus.retry, JobStatus.canceled}:
        raise HTTPException(409, 'Повторно поставить можно только dead/retry/canceled job.')
    previous_status = row.status.value
    row.status = JobStatus.queued
    row.attempts = 0
    row.available_at = datetime.now(timezone.utc)
    row.locked_at = None
    row.heartbeat_at = None
    row.locked_by = ''
    row.attempt_id = ''
    row.finished_at = None
    row.last_error = ''
    db.add(SecurityEvent(user_id=admin.id,event_type='admin_job_requeued',success=True,subject_hash=hashlib.sha256(row.id.encode()).hexdigest(),user_agent='admin-api'))
    db.commit(); db.refresh(row)
    return {'job': _job_public(row), 'previous_status': previous_status, 'requeued': True}


@router.get("/admin/summary")
def summary(_: User = Depends(require_platform_summary), db: Session = Depends(get_db)):
    users = db.scalar(select(func.count()).select_from(User)) or 0
    active_users = db.scalar(select(func.count()).select_from(User).where(User.is_active.is_(True))) or 0
    workspaces = db.scalar(select(func.count()).select_from(Workspace)) or 0
    active_subscriptions = db.scalar(select(func.count()).select_from(Subscription).where(Subscription.status == SubscriptionStatus.active)) or 0
    trial_subscriptions = db.scalar(select(func.count()).select_from(Subscription).where(Subscription.status == SubscriptionStatus.trial)) or 0
    return {"users": users,"active_users": active_users,"workspaces": workspaces,"active_subscriptions": active_subscriptions,"trial_subscriptions": trial_subscriptions}


def _platform_overview(db: Session, *, as_of: datetime, lease_seconds: int) -> dict:
    """Build the aggregate-only staff read model with a fixed query count."""
    new_users_since = as_of - timedelta(days=7)
    succeeded_jobs_since = as_of - timedelta(hours=24)
    stale_before = as_of - timedelta(seconds=lease_seconds)
    lease_timestamp = func.coalesce(BackgroundJob.heartbeat_at, BackgroundJob.locked_at)
    backlog = BackgroundJob.status.in_([JobStatus.queued, JobStatus.retry])

    user_counts = db.execute(select(
        func.count(User.id),
        func.coalesce(func.sum(case((User.is_active.is_(True), 1), else_=0)), 0),
        func.coalesce(func.sum(case((and_(User.created_at >= new_users_since, User.created_at <= as_of), 1), else_=0)), 0),
    )).one()

    operation_counts = db.execute(select(
        select(func.count(Workspace.id)).scalar_subquery(),
        select(func.count(Store.id)).where(Store.is_active.is_(True)).scalar_subquery(),
        select(func.count(func.distinct(Store.id))).select_from(Store).join(
            MarketplaceConnection, MarketplaceConnection.store_id == Store.id,
        ).where(
            Store.is_active.is_(True),
            MarketplaceConnection.enabled.is_(True),
            MarketplaceConnection.marketplace == "wildberries",
        ).scalar_subquery(),
    )).one()

    job_counts = db.execute(select(
        *[
            func.coalesce(func.sum(case((BackgroundJob.status == status_value, 1), else_=0)), 0)
            for status_value in (JobStatus.queued, JobStatus.running, JobStatus.retry, JobStatus.dead)
        ],
        func.coalesce(func.sum(case((and_(
            BackgroundJob.status == JobStatus.succeeded,
            BackgroundJob.finished_at >= succeeded_jobs_since,
            BackgroundJob.finished_at <= as_of,
        ), 1), else_=0)), 0),
        func.coalesce(func.sum(case((and_(backlog, BackgroundJob.available_at <= as_of), 1), else_=0)), 0),
        func.coalesce(func.sum(case((and_(backlog, BackgroundJob.available_at > as_of), 1), else_=0)), 0),
        func.min(case((and_(backlog, BackgroundJob.available_at <= as_of), BackgroundJob.available_at))),
        func.coalesce(func.sum(case((and_(BackgroundJob.status == JobStatus.running, lease_timestamp >= stale_before), 1), else_=0)), 0),
        func.coalesce(func.sum(case((and_(BackgroundJob.status == JobStatus.running, lease_timestamp < stale_before), 1), else_=0)), 0),
        func.coalesce(func.sum(case((and_(
            BackgroundJob.status == JobStatus.running,
            BackgroundJob.heartbeat_at.is_(None),
            BackgroundJob.locked_at.is_(None),
        ), 1), else_=0)), 0),
    )).one()

    oldest_ready = job_counts[7]
    if oldest_ready is not None and oldest_ready.tzinfo is None:
        oldest_ready = oldest_ready.replace(tzinfo=timezone.utc)
    oldest_ready_age = max(0, int((as_of - oldest_ready).total_seconds())) if oldest_ready else None

    return {
        "as_of": as_of,
        "windows": {
            "new_users_since": new_users_since,
            "new_users_until": as_of,
            "succeeded_jobs_since": succeeded_jobs_since,
            "succeeded_jobs_until": as_of,
        },
        "access": {"scope": "platform_aggregate", "source": "database_aggregates"},
        "users": {"total": user_counts[0], "enabled": user_counts[1], "new_7d": user_counts[2]},
        "operations": {"workspaces": operation_counts[0], "active_stores": operation_counts[1], "connections_saved": operation_counts[2]},
        "jobs": {
            "queued": job_counts[0], "running": job_counts[1], "retry": job_counts[2], "dead": job_counts[3],
            "succeeded_24h": job_counts[4],
            "backlog": {"ready": job_counts[5], "future_cooldown": job_counts[6], "oldest_ready_age_seconds": oldest_ready_age},
            "running_leases": {"fresh": job_counts[8], "stale": job_counts[9], "missing_timestamp": job_counts[10], "lease_seconds": lease_seconds},
        },
        "availability": {
            "confirmed_revenue": None,
            "mrr": None,
            "ai_actual_cost": None,
            "task_assignments": None,
            "live_provider_health": "unknown",
            "redis_health": "unknown",
            "vercel_health": "unknown",
            "worker_health": "unknown",
        },
        "limitations": [
            "multi_query_read_model",
            "saved_wb_connection_is_not_provider_verification",
            "live_services_not_probed",
            "business_metrics_not_available",
        ],
    }


@router.get("/admin/overview")
def platform_overview(_: User = Depends(require_platform_summary), db: Session = Depends(get_db)):
    as_of = datetime.now(timezone.utc)
    lease_seconds = max(30, get_settings().job_lease_seconds)
    return _platform_overview(db, as_of=as_of, lease_seconds=lease_seconds)


@router.get("/admin/users")
def users(_: User = Depends(require_platform_admin), db: Session = Depends(get_db)):
    rows = db.scalars(select(User).order_by(User.created_at.desc()).limit(200)).all()
    result = []
    for user in rows:
        membership = db.scalar(select(Membership).where(Membership.user_id == user.id))
        workspace = db.get(Workspace, membership.workspace_id) if membership else None
        subscription = _latest_subscription(db, membership.workspace_id) if membership else None
        result.append({"id": user.id,"email": user.email,"full_name": user.full_name,"is_active": user.is_active,"email_verified": user.email_verified,"created_at": user.created_at,"workspace_id": workspace.id if workspace else None,"workspace_name": workspace.name if workspace else None,"role": membership.role.value if membership else None,"plan_code": subscription.plan_code if subscription else "none","subscription_status": subscription.status.value if subscription else "none"})
    return {"items": result, "limit": 200}


@router.get("/admin/team")
def platform_team(_: User = Depends(require_platform_admin), db: Session = Depends(get_db)):
    rows = db.execute(
        select(PlatformStaffRole, User)
        .join(User, User.id == PlatformStaffRole.user_id)
        .where(PlatformStaffRole.revoked_at.is_(None))
        .order_by(PlatformStaffRole.role, User.email)
    ).all()
    return {"items": [
        {
            "user_id": role.user_id,
            "email": user.email,
            "full_name": user.full_name,
            "role": role.role.value,
            "is_active": user.is_active,
            "email_verified": user.email_verified,
            "granted_at": role.granted_at,
        }
        for role, user in rows
    ]}


@router.post("/admin/team/grants", status_code=status.HTTP_201_CREATED)
def grant_platform_team_member(payload: PlatformGrantRequest, admin: User = Depends(require_platform_admin_step_up), db: Session = Depends(get_db)):
    role = grant_project_manager(db, actor_id=admin.id, target_user_id=payload.user_id)
    db.add(SecurityEvent(
        user_id=admin.id,
        event_type="platform_staff.granted",
        success=True,
        subject_hash=hashlib.sha256(role.user_id.encode()).hexdigest(),
        user_agent="admin-api",
    ))
    db.commit()
    return {"user_id": role.user_id, "role": role.role.value, "revoked_at": None}


@router.delete("/admin/team/grants/{user_id}")
def revoke_platform_team_member(user_id: str, admin: User = Depends(require_platform_admin_step_up), db: Session = Depends(get_db)):
    role = revoke_platform_role(db, actor_id=admin.id, target_user_id=user_id)
    db.add(SecurityEvent(
        user_id=admin.id,
        event_type="platform_staff.revoked",
        success=True,
        subject_hash=hashlib.sha256(role.user_id.encode()).hexdigest(),
        user_agent="admin-api",
    ))
    db.commit()
    return {"user_id": role.user_id, "role": role.role.value, "revoked_at": role.revoked_at}


@router.patch("/admin/users/{user_id}/status")
def set_user_status(user_id: str, active: bool, admin: User = Depends(require_platform_admin_step_up), db: Session = Depends(get_db)):
    if user_id == admin.id and not active: raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Administrator cannot disable own account")
    user = set_user_active_serialized(db, actor_id=admin.id, target_user_id=user_id, active=active)
    db.add(SecurityEvent(user_id=admin.id,event_type='admin_user_status_changed',success=True,subject_hash=hashlib.sha256(user.id.encode()).hexdigest(),user_agent='admin-api'))
    db.commit(); return {"id": user.id, "is_active": user.is_active}


@router.patch("/admin/workspaces/{workspace_id}/plan")
def set_workspace_plan(workspace_id: str, plan_code: str, admin: User = Depends(require_platform_admin_step_up), db: Session = Depends(get_db)):
    if plan_code not in VALID_PLANS: raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unknown plan")
    with serialized_platform_access(db):
        require_effective_owner_after_lock(db, admin.id)
        workspace = db.get(Workspace, workspace_id)
        if workspace is None: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
        subscription = _latest_subscription(db, workspace_id)
        target_status = SubscriptionStatus.trial if plan_code == "trial" else SubscriptionStatus.active
        if subscription is None:
            subscription = Subscription(workspace_id=workspace_id, plan_code=plan_code, status=target_status, provider="admin_override"); db.add(subscription)
        else:
            subscription.plan_code = plan_code; subscription.status = target_status; subscription.provider = subscription.provider or "admin_override"
        subscription.current_period_started_at = None; subscription.current_period_expires_at = None; subscription.cancel_at_period_end = False; subscription.canceled_at = None
        db.add(SecurityEvent(user_id=admin.id,event_type='admin_workspace_plan_changed',success=True,subject_hash=hashlib.sha256(workspace_id.encode()).hexdigest(),user_agent='admin-api'))
        db.commit()
    return {"workspace_id": workspace_id, "plan_code": plan_code, "status": target_status.value}
