from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_db
from .models import Membership, MembershipRole, Subscription, SubscriptionStatus, User, Workspace
from .schemas import AccountResponse, LoginRequest, RegisterRequest, TokenResponse
from .security import create_access_token, get_current_user, hash_password, is_platform_admin, verify_password

router = APIRouter()

PLANS = [
    {
        "code": "trial",
        "name": "Trial",
        "price_monthly_rub": 0,
        "stores": 1,
        "users": 1,
        "ai_generation": "limited",
        "autopilot": "recommendations",
    },
    {
        "code": "pro",
        "name": "PRO",
        "price_monthly_rub": 4990,
        "stores": 3,
        "users": 3,
        "ai_generation": "extended",
        "autopilot": "assisted",
    },
    {
        "code": "business",
        "name": "Business",
        "price_monthly_rub": 12990,
        "stores": 10,
        "users": 10,
        "ai_generation": "priority",
        "autopilot": "advanced",
    },
]


@router.get("/billing/plans")
def plans():
    return {"currency": "RUB", "provider": "not_configured", "plans": PLANS}


@router.post("/auth/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    email = payload.email.lower().strip()
    if db.scalar(select(User.id).where(User.email == email)) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already registered")

    user = User(email=email, password_hash=hash_password(payload.password), full_name=payload.full_name.strip())
    workspace = Workspace(name=payload.workspace_name.strip())
    db.add_all([user, workspace])
    db.flush()
    db.add(Membership(user_id=user.id, workspace_id=workspace.id, role=MembershipRole.owner))
    db.add(Subscription(workspace_id=workspace.id, plan_code="trial", status=SubscriptionStatus.trial))
    db.commit()
    return TokenResponse(access_token=create_access_token(user.id))


@router.post("/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    email = payload.email.lower().strip()
    user = db.scalar(select(User).where(User.email == email, User.is_active.is_(True)))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    return TokenResponse(access_token=create_access_token(user.id))


@router.get("/auth/me", response_model=AccountResponse)
def me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    membership = db.scalar(select(Membership).where(Membership.user_id == current_user.id))
    if membership is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Workspace membership is missing")
    workspace = db.get(Workspace, membership.workspace_id)
    subscription = db.scalar(
        select(Subscription)
        .where(Subscription.workspace_id == membership.workspace_id)
        .order_by(Subscription.created_at.desc())
    )
    return AccountResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        email_verified=current_user.email_verified,
        workspace_id=workspace.id,
        workspace_name=workspace.name,
        role=membership.role.value,
        plan_code=subscription.plan_code if subscription else "none",
        subscription_status=subscription.status.value if subscription else "none",
        is_platform_admin=is_platform_admin(current_user),
    )
