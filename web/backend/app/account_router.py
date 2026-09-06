import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db
from .models import (
    AccountActionToken,
    AccountTokenPurpose,
    Membership,
    MembershipRole,
    Subscription,
    SubscriptionStatus,
    User,
    Workspace,
)
from .schemas import (
    AccountResponse,
    EmailRequest,
    LoginRequest,
    PasswordResetConfirmRequest,
    RegisterRequest,
    TokenActionRequest,
    TokenResponse,
)
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


def _token_hash(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _create_account_token(db: Session, user: User, purpose: AccountTokenPurpose, lifetime: timedelta) -> str:
    now = datetime.now(timezone.utc)
    db.execute(
        update(AccountActionToken)
        .where(
            AccountActionToken.user_id == user.id,
            AccountActionToken.purpose == purpose,
            AccountActionToken.used_at.is_(None),
        )
        .values(used_at=now)
    )
    raw_token = secrets.token_urlsafe(48)
    db.add(
        AccountActionToken(
            user_id=user.id,
            purpose=purpose,
            token_hash=_token_hash(raw_token),
            expires_at=now + lifetime,
        )
    )
    db.commit()
    return raw_token


def _consume_account_token(db: Session, raw_token: str, purpose: AccountTokenPurpose) -> tuple[AccountActionToken, User]:
    token = db.scalar(
        select(AccountActionToken).where(
            AccountActionToken.token_hash == _token_hash(raw_token),
            AccountActionToken.purpose == purpose,
            AccountActionToken.used_at.is_(None),
        )
    )
    if token is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or already used token")

    expires_at = token.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= datetime.now(timezone.utc):
        token.used_at = datetime.now(timezone.utc)
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token has expired")

    user = db.get(User, token.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Account is unavailable")
    return token, user


def _delivery_response(raw_token: str, purpose: str) -> dict:
    settings = get_settings()
    result = {
        "ok": True,
        "message": "If the account exists, instructions will be sent to its email address.",
        "delivery": "email_provider_not_configured",
    }
    # Development-only escape hatch for local/CI testing. Production never exposes raw action tokens.
    if settings.environment.lower() in {"development", "test", "testing"}:
        result["development_token"] = raw_token
        result["purpose"] = purpose
    return result


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


@router.post("/auth/email-verification/request")
def request_email_verification(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.email_verified:
        return {"ok": True, "message": "Email is already verified", "delivery": "not_required"}
    settings = get_settings()
    raw_token = _create_account_token(
        db,
        current_user,
        AccountTokenPurpose.verify_email,
        timedelta(hours=settings.email_verification_hours),
    )
    return _delivery_response(raw_token, AccountTokenPurpose.verify_email.value)


@router.post("/auth/email-verification/confirm")
def confirm_email_verification(payload: TokenActionRequest, db: Session = Depends(get_db)):
    token, user = _consume_account_token(db, payload.token, AccountTokenPurpose.verify_email)
    user.email_verified = True
    token.used_at = datetime.now(timezone.utc)
    db.commit()
    return {"ok": True, "email_verified": True}


@router.post("/auth/password-reset/request")
def request_password_reset(payload: EmailRequest, db: Session = Depends(get_db)):
    email = payload.email.lower().strip()
    user = db.scalar(select(User).where(User.email == email, User.is_active.is_(True)))
    if user is None:
        return {
            "ok": True,
            "message": "If the account exists, instructions will be sent to its email address.",
            "delivery": "not_disclosed",
        }
    settings = get_settings()
    raw_token = _create_account_token(
        db,
        user,
        AccountTokenPurpose.reset_password,
        timedelta(minutes=settings.password_reset_minutes),
    )
    return _delivery_response(raw_token, AccountTokenPurpose.reset_password.value)


@router.post("/auth/password-reset/confirm")
def confirm_password_reset(payload: PasswordResetConfirmRequest, db: Session = Depends(get_db)):
    token, user = _consume_account_token(db, payload.token, AccountTokenPurpose.reset_password)
    user.password_hash = hash_password(payload.new_password)
    token.used_at = datetime.now(timezone.utc)
    db.execute(
        update(AccountActionToken)
        .where(
            AccountActionToken.user_id == user.id,
            AccountActionToken.used_at.is_(None),
        )
        .values(used_at=datetime.now(timezone.utc))
    )
    db.commit()
    return {"ok": True, "message": "Password has been updated"}


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
