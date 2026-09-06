from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .account_router import PLANS
from .db import get_db
from .models import Membership, Subscription, SubscriptionStatus, User, Workspace
from .security import require_platform_admin

router = APIRouter()
VALID_PLANS = {plan["code"] for plan in PLANS}


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
        "billing_provider": "not_configured",
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
def set_user_status(user_id: str, active: bool, admin: User = Depends(require_platform_admin), db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.id == admin.id and not active:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Administrator cannot disable own account")
    user.is_active = active
    db.commit()
    return {"id": user.id, "is_active": user.is_active}


@router.patch("/admin/workspaces/{workspace_id}/plan")
def set_workspace_plan(workspace_id: str, plan_code: str, _: User = Depends(require_platform_admin), db: Session = Depends(get_db)):
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
    db.commit()
    return {"workspace_id": workspace_id, "plan_code": plan_code, "status": target_status.value}
