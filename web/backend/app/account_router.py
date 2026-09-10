import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from .config import get_settings
from .billing_service import entitlement_snapshot, latest_subscription, public_plans
from .db import get_db
from .models import (
    AccountActionToken,
    AccountTokenPurpose,
    Membership,
    MembershipRole,
    MfaLoginChallenge,
    SecurityEvent,
    Subscription,
    SubscriptionStatus,
    User,
    UserMfa,
    UserSession,
    Workspace,
)
from .schemas import (
    AccountResponse,
    EmailRequest,
    LoginRequest,
    MfaCodeRequest,
    MfaDisableRequest,
    MfaLoginRequest,
    MfaPasswordRequest,
    PasswordResetConfirmRequest,
    RegisterRequest,
    StepUpRequest,
    TokenActionRequest,
    TokenResponse,
)
from .mfa_service import (
    consume_recovery_code,
    decrypt_secret,
    encrypt_secret,
    generate_recovery_codes,
    generate_secret,
    matched_totp_step,
    provisioning_uri,
    verify_totp,
)
from .security import (
    create_access_token,
    get_current_session,
    get_current_user,
    hash_password,
    is_platform_admin,
    step_up_valid_until,
    verify_password,
)

router = APIRouter()


def _token_hash(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _privacy_hash(value: str) -> str:
    settings = get_settings()
    return hashlib.sha256(f"{settings.jwt_secret}:{value}".encode("utf-8")).hexdigest()


def _request_fingerprint(request: Request) -> tuple[str, str]:
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    host = forwarded or (request.client.host if request.client else "")
    user_agent = request.headers.get("user-agent", "")[:320]
    return _privacy_hash(host) if host else "", user_agent


def _record_security_event(db: Session, request: Request, event_type: str, success: bool, user: User | None = None, subject: str = "") -> None:
    ip_hash, user_agent = _request_fingerprint(request)
    db.add(SecurityEvent(
        user_id=user.id if user else None,
        event_type=event_type,
        success=success,
        subject_hash=_privacy_hash(subject.lower().strip()) if subject else "",
        ip_hash=ip_hash,
        user_agent=user_agent,
    ))


def _create_session(db: Session, request: Request, user: User, mfa_verified: bool = False) -> str:
    settings = get_settings()
    ip_hash, user_agent = _request_fingerprint(request)
    now = datetime.now(timezone.utc)
    session = UserSession(
        user_id=user.id,
        user_agent=user_agent,
        ip_hash=ip_hash,
        last_seen_at=now,
        expires_at=now + timedelta(days=settings.session_days),
        mfa_verified_at=now if mfa_verified else None,
    )
    db.add(session)
    _record_security_event(db, request, "session_created", True, user=user)
    db.commit()
    return create_access_token(user.id, session.id)


def _new_mfa_challenge(db: Session, request: Request, user: User) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    db.execute(update(MfaLoginChallenge).where(
        MfaLoginChallenge.user_id == user.id,
        MfaLoginChallenge.used_at.is_(None),
    ).values(used_at=now))
    raw_token = secrets.token_urlsafe(48)
    db.add(MfaLoginChallenge(
        user_id=user.id,
        token_hash=_token_hash(raw_token),
        expires_at=now + timedelta(minutes=settings.mfa_challenge_minutes),
    ))
    _record_security_event(db, request, "mfa_challenge_created", True, user=user)
    db.commit()
    return raw_token


def _verify_mfa_code(mfa: UserMfa, code: str) -> bool:
    step = matched_totp_step(decrypt_secret(mfa.secret_ciphertext), code)
    if step is not None and (mfa.last_totp_step is None or step > mfa.last_totp_step):
        mfa.last_totp_step = step
        return True
    remaining = consume_recovery_code(mfa.recovery_code_hashes or [], code)
    if remaining is None:
        return False
    mfa.recovery_code_hashes = remaining
    return True


def _mfa_login_is_limited(db: Session, request: Request, user: User) -> bool:
    settings = get_settings()
    since = datetime.now(timezone.utc) - timedelta(minutes=settings.login_attempt_window_minutes)
    ip_hash, _ = _request_fingerprint(request)
    conditions = (SecurityEvent.event_type == "mfa_login", SecurityEvent.success.is_(False), SecurityEvent.created_at >= since)
    subject_failures = db.scalar(select(func.count(SecurityEvent.id)).where(
        *conditions, SecurityEvent.subject_hash == _privacy_hash(user.email),
    )) or 0
    ip_failures = db.scalar(select(func.count(SecurityEvent.id)).where(
        *conditions, SecurityEvent.ip_hash == ip_hash,
    )) or 0
    return subject_failures >= settings.mfa_attempt_limit or ip_failures >= settings.login_ip_max_failures


def _login_is_limited(db: Session, email: str, request: Request) -> bool:
    settings = get_settings()
    since = datetime.now(timezone.utc) - timedelta(minutes=settings.login_attempt_window_minutes)
    ip_hash, _ = _request_fingerprint(request)
    subject_failures = db.scalar(
        select(func.count(SecurityEvent.id)).where(
            SecurityEvent.event_type == "login",
            SecurityEvent.success.is_(False),
            SecurityEvent.subject_hash == _privacy_hash(email),
            SecurityEvent.created_at >= since,
        )
    ) or 0
    ip_failures = db.scalar(
        select(func.count(SecurityEvent.id)).where(
            SecurityEvent.event_type == "login",
            SecurityEvent.success.is_(False),
            SecurityEvent.ip_hash == ip_hash,
            SecurityEvent.created_at >= since,
        )
    ) or 0
    return subject_failures >= settings.login_attempt_max_failures or ip_failures >= settings.login_ip_max_failures


def _account_action_is_limited(db: Session, request: Request, event_type: str, subject: str) -> bool:
    settings = get_settings()
    since = datetime.now(timezone.utc) - timedelta(minutes=settings.account_action_window_minutes)
    ip_hash, _ = _request_fingerprint(request)
    subject_hash = _privacy_hash(subject.lower().strip())
    subject_count = db.scalar(select(func.count(SecurityEvent.id)).where(
        SecurityEvent.event_type == event_type,
        SecurityEvent.subject_hash == subject_hash,
        SecurityEvent.created_at >= since,
    )) or 0
    ip_count = db.scalar(select(func.count(SecurityEvent.id)).where(
        SecurityEvent.event_type == event_type,
        SecurityEvent.ip_hash == ip_hash,
        SecurityEvent.created_at >= since,
    )) or 0
    return subject_count >= settings.account_action_subject_limit or ip_count >= settings.account_action_ip_limit


def _create_account_token(db: Session, user: User, purpose: AccountTokenPurpose, lifetime: timedelta) -> str:
    now = datetime.now(timezone.utc)
    db.execute(
        update(AccountActionToken)
        .where(AccountActionToken.user_id == user.id, AccountActionToken.purpose == purpose, AccountActionToken.used_at.is_(None))
        .values(used_at=now)
    )
    raw_token = secrets.token_urlsafe(48)
    db.add(AccountActionToken(user_id=user.id, purpose=purpose, token_hash=_token_hash(raw_token), expires_at=now + lifetime))
    db.commit()
    return raw_token


def _consume_account_token(db: Session, raw_token: str, purpose: AccountTokenPurpose) -> tuple[AccountActionToken, User]:
    token = db.scalar(select(AccountActionToken).where(
        AccountActionToken.token_hash == _token_hash(raw_token),
        AccountActionToken.purpose == purpose,
        AccountActionToken.used_at.is_(None),
    ))
    if token is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or already used token")
    expires_at = token.expires_at if token.expires_at.tzinfo else token.expires_at.replace(tzinfo=timezone.utc)
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
    result = {"ok": True, "message": "If the account exists, instructions will be sent to its email address.", "delivery": "email_provider_not_configured"}
    if settings.environment.lower() in {"development", "test", "testing"}:
        result["development_token"] = raw_token
        result["purpose"] = purpose
    return result


@router.get("/billing/plans")
def plans():
    settings = get_settings()
    return {"currency": "RUB", "provider": settings.billing_provider, "checkout_available": settings.billing_is_configured, "plans": public_plans()}


@router.get("/billing/subscription")
def billing_subscription(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    membership = db.scalar(select(Membership).where(Membership.user_id == current_user.id))
    if membership is None:
        raise HTTPException(status_code=409, detail="Workspace membership is missing")
    subscription = latest_subscription(db, membership.workspace_id)
    settings = get_settings()
    return {
        "workspace_id": membership.workspace_id,
        "provider": subscription.provider or settings.billing_provider,
        "checkout_available": settings.billing_is_configured,
        **entitlement_snapshot(subscription),
    }


class CheckoutRequest(BaseModel):
    plan_code: str
    accepted_terms: bool = False


@router.post("/billing/checkout")
def create_billing_checkout(payload: CheckoutRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if payload.plan_code not in {"pro", "business"}:
        raise HTTPException(status_code=422, detail="Выберите платный тариф PRO или Business.")
    if not payload.accepted_terms:
        raise HTTPException(status_code=422, detail="Подтвердите условия подписки и автоматического продления.")
    membership = db.scalar(select(Membership).where(Membership.user_id == current_user.id))
    if membership is None:
        raise HTTPException(status_code=409, detail="Workspace membership is missing")
    if membership.role != MembershipRole.owner:
        raise HTTPException(status_code=403, detail="Оформить подписку может только владелец рабочего пространства.")
    settings = get_settings()
    if not settings.billing_is_configured:
        raise HTTPException(status_code=503, detail="Платёжный провайдер ещё не подключён. Trial продолжает работать без привязки карты.")
    raise HTTPException(status_code=503, detail="Адаптер выбранного платёжного провайдера ещё не активирован.")


@router.post("/auth/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    email = payload.email.lower().strip()
    if db.scalar(select(User.id).where(User.email == email)) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already registered")
    user = User(email=email, password_hash=hash_password(payload.password), full_name=payload.full_name.strip())
    workspace = Workspace(name=payload.workspace_name.strip())
    db.add_all([user, workspace])
    db.flush()
    db.add(Membership(user_id=user.id, workspace_id=workspace.id, role=MembershipRole.owner))
    db.add(Subscription(workspace_id=workspace.id, plan_code="trial", status=SubscriptionStatus.trial))
    _record_security_event(db, request, "registration", True, user=user, subject=email)
    db.commit()
    return TokenResponse(access_token=_create_session(db, request, user))


@router.post("/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    email = payload.email.lower().strip()
    if _login_is_limited(db, email, request):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many failed login attempts. Try again later.")
    user = db.scalar(select(User).where(User.email == email, User.is_active.is_(True)))
    if user is None or not verify_password(payload.password, user.password_hash):
        _record_security_event(db, request, "login", False, user=user, subject=email)
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    mfa = db.get(UserMfa, user.id)
    if mfa is not None and mfa.enabled:
        return TokenResponse(mfa_required=True, mfa_challenge_token=_new_mfa_challenge(db, request, user))
    _record_security_event(db, request, "login", True, user=user, subject=email)
    return TokenResponse(access_token=_create_session(db, request, user))


@router.post("/auth/mfa/login", response_model=TokenResponse)
def login_mfa(payload: MfaLoginRequest, request: Request, db: Session = Depends(get_db)):
    challenge = db.scalar(select(MfaLoginChallenge).where(
        MfaLoginChallenge.token_hash == _token_hash(payload.challenge_token),
        MfaLoginChallenge.used_at.is_(None),
    ))
    if challenge is None:
        raise HTTPException(status_code=400, detail="MFA challenge is invalid or already used")
    now = datetime.now(timezone.utc)
    expires_at = challenge.expires_at if challenge.expires_at.tzinfo else challenge.expires_at.replace(tzinfo=timezone.utc)
    settings = get_settings()
    if expires_at <= now or challenge.attempts >= settings.mfa_attempt_limit:
        challenge.used_at = now
        db.commit()
        raise HTTPException(status_code=400, detail="MFA challenge has expired")
    user = db.get(User, challenge.user_id)
    mfa = db.get(UserMfa, challenge.user_id)
    if user is None or not user.is_active or mfa is None or not mfa.enabled:
        challenge.used_at = now
        db.commit()
        raise HTTPException(status_code=400, detail="MFA challenge is unavailable")
    if _mfa_login_is_limited(db, request, user):
        challenge.used_at = now
        db.commit()
        raise HTTPException(status_code=429, detail="Too many failed MFA attempts. Try again later.")
    if not _verify_mfa_code(mfa, payload.code):
        challenge.attempts += 1
        if challenge.attempts >= settings.mfa_attempt_limit:
            challenge.used_at = now
        _record_security_event(db, request, "mfa_login", False, user=user, subject=user.email)
        db.commit()
        raise HTTPException(status_code=401, detail="Invalid authentication code")
    challenge.used_at = now
    _record_security_event(db, request, "mfa_login", True, user=user, subject=user.email)
    _record_security_event(db, request, "login", True, user=user, subject=user.email)
    return TokenResponse(access_token=_create_session(db, request, user, mfa_verified=True))


@router.get("/auth/mfa/status")
def mfa_status(current_user: User = Depends(get_current_user), current_session: UserSession = Depends(get_current_session), db: Session = Depends(get_db)):
    mfa = db.get(UserMfa, current_user.id)
    return {
        "enabled": bool(mfa and mfa.enabled),
        "setup_pending": bool(mfa and not mfa.enabled),
        "recovery_codes_remaining": len(mfa.recovery_code_hashes or []) if mfa and mfa.enabled else 0,
        "current_session_verified": current_session.mfa_verified_at is not None,
    }


@router.post("/auth/mfa/setup")
def setup_mfa(payload: MfaPasswordRequest, request: Request, current_user: User = Depends(get_current_user), current_session: UserSession = Depends(get_current_session), db: Session = Depends(get_db)):
    if _account_action_is_limited(db, request, "mfa_setup", current_user.email):
        raise HTTPException(status_code=429, detail="Too many MFA setup attempts. Try again later.")
    if not verify_password(payload.password, current_user.password_hash):
        _record_security_event(db, request, "mfa_setup", False, user=current_user)
        db.commit()
        raise HTTPException(status_code=401, detail="Current password is invalid")
    existing = db.get(UserMfa, current_user.id)
    if existing is not None and existing.enabled:
        raise HTTPException(status_code=409, detail="Disable the current MFA configuration before replacing it")
    secret = generate_secret()
    now = datetime.now(timezone.utc)
    if existing is None:
        existing = UserMfa(user_id=current_user.id, secret_ciphertext=encrypt_secret(secret), enabled=False, recovery_code_hashes=[], pending_created_at=now)
        db.add(existing)
    else:
        existing.secret_ciphertext = encrypt_secret(secret)
        existing.enabled = False
        existing.recovery_code_hashes = []
        existing.last_totp_step = None
        existing.pending_created_at = now
        existing.confirmed_at = None
    _record_security_event(db, request, "mfa_setup", True, user=current_user)
    db.commit()
    return {"ok": True, "secret": secret, "provisioning_uri": provisioning_uri(secret, current_user.email)}


@router.post("/auth/mfa/confirm")
def confirm_mfa(payload: MfaCodeRequest, request: Request, current_user: User = Depends(get_current_user), current_session: UserSession = Depends(get_current_session), db: Session = Depends(get_db)):
    if _account_action_is_limited(db, request, "mfa_confirm", current_user.email):
        raise HTTPException(status_code=429, detail="Too many MFA confirmation attempts. Try again later.")
    mfa = db.get(UserMfa, current_user.id)
    if mfa is None or mfa.enabled:
        raise HTTPException(status_code=409, detail="MFA setup is not pending")
    pending_at = mfa.pending_created_at if mfa.pending_created_at.tzinfo else mfa.pending_created_at.replace(tzinfo=timezone.utc)
    if pending_at + timedelta(minutes=get_settings().mfa_setup_minutes) <= datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="MFA setup has expired. Start again.")
    if not verify_totp(decrypt_secret(mfa.secret_ciphertext), payload.code):
        _record_security_event(db, request, "mfa_confirm", False, user=current_user)
        db.commit()
        raise HTTPException(status_code=401, detail="Invalid authentication code")
    now = datetime.now(timezone.utc)
    raw_codes, code_hashes = generate_recovery_codes()
    mfa.enabled = True
    mfa.recovery_code_hashes = code_hashes
    mfa.confirmed_at = now
    current_session.mfa_verified_at = now
    current_session.step_up_verified_at = None
    db.execute(update(UserSession).where(
        UserSession.user_id == current_user.id,
        UserSession.id != current_session.id,
        UserSession.revoked_at.is_(None),
    ).values(revoked_at=now))
    _record_security_event(db, request, "mfa_enabled", True, user=current_user)
    db.commit()
    return {"ok": True, "enabled": True, "recovery_codes": raw_codes}


@router.post("/auth/mfa/disable")
def disable_mfa(payload: MfaDisableRequest, request: Request, current_user: User = Depends(get_current_user), current_session: UserSession = Depends(get_current_session), db: Session = Depends(get_db)):
    if _account_action_is_limited(db, request, "mfa_disable", current_user.email):
        raise HTTPException(status_code=429, detail="Too many MFA disable attempts. Try again later.")
    mfa = db.get(UserMfa, current_user.id)
    if mfa is None or not mfa.enabled:
        raise HTTPException(status_code=409, detail="MFA is not enabled")
    if not verify_password(payload.password, current_user.password_hash) or not _verify_mfa_code(mfa, payload.code):
        _record_security_event(db, request, "mfa_disable", False, user=current_user)
        db.commit()
        raise HTTPException(status_code=401, detail="Password or authentication code is invalid")
    now = datetime.now(timezone.utc)
    db.delete(mfa)
    current_session.mfa_verified_at = None
    current_session.step_up_verified_at = None
    db.execute(update(UserSession).where(
        UserSession.user_id == current_user.id,
        UserSession.id != current_session.id,
        UserSession.revoked_at.is_(None),
    ).values(revoked_at=now))
    _record_security_event(db, request, "mfa_disabled", True, user=current_user)
    db.commit()
    return {"ok": True, "enabled": False}


@router.get("/auth/step-up/status")
def step_up_status(current_user: User = Depends(get_current_user), current_session: UserSession = Depends(get_current_session), db: Session = Depends(get_db)):
    valid_until = step_up_valid_until(current_session)
    now = datetime.now(timezone.utc)
    mfa = db.get(UserMfa, current_user.id)
    return {
        "verified": bool(valid_until and valid_until > now),
        "valid_until": valid_until if valid_until and valid_until > now else None,
        "mfa_required": bool(mfa and mfa.enabled),
        "lifetime_minutes": get_settings().step_up_minutes,
    }


@router.post("/auth/step-up")
def verify_step_up(payload: StepUpRequest, request: Request, current_user: User = Depends(get_current_user), current_session: UserSession = Depends(get_current_session), db: Session = Depends(get_db)):
    if _account_action_is_limited(db, request, "step_up", current_user.email):
        raise HTTPException(status_code=429, detail="Too many verification attempts. Try again later.")
    mfa = db.get(UserMfa, current_user.id)
    password_ok = verify_password(payload.password, current_user.password_hash)
    second_factor_ok = False
    if password_ok:
        second_factor_ok = not (mfa and mfa.enabled) or bool(payload.code and _verify_mfa_code(mfa, payload.code))
    if not password_ok or not second_factor_ok:
        _record_security_event(db, request, "step_up", False, user=current_user, subject=current_user.email)
        db.commit()
        raise HTTPException(status_code=401, detail="Password or authentication code is invalid")
    now = datetime.now(timezone.utc)
    current_session.step_up_verified_at = now
    _record_security_event(db, request, "step_up", True, user=current_user, subject=current_user.email)
    db.commit()
    return {"ok": True, "verified": True, "valid_until": step_up_valid_until(current_session)}


@router.get("/auth/sessions")
def sessions(current_user: User = Depends(get_current_user), current_session: UserSession = Depends(get_current_session), db: Session = Depends(get_db)):
    rows = db.scalars(select(UserSession).where(UserSession.user_id == current_user.id).order_by(UserSession.created_at.desc())).all()
    return {"sessions": [{
        "id": row.id,
        "current": row.id == current_session.id,
        "user_agent": row.user_agent,
        "created_at": row.created_at,
        "last_seen_at": row.last_seen_at,
        "expires_at": row.expires_at,
        "revoked": row.revoked_at is not None,
        "mfa_verified": row.mfa_verified_at is not None,
        "step_up_verified": bool(step_up_valid_until(row) and step_up_valid_until(row) > datetime.now(timezone.utc)),
    } for row in rows]}


@router.delete("/auth/sessions/{session_id}")
def revoke_session(session_id: str, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    target = db.scalar(select(UserSession).where(UserSession.id == session_id, UserSession.user_id == current_user.id))
    if target is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if target.revoked_at is None:
        target.revoked_at = datetime.now(timezone.utc)
        _record_security_event(db, request, "session_revoked", True, user=current_user)
        db.commit()
    return {"ok": True}


@router.post("/auth/logout")
def logout(request: Request, current_user: User = Depends(get_current_user), current_session: UserSession = Depends(get_current_session), db: Session = Depends(get_db)):
    current_session.revoked_at = datetime.now(timezone.utc)
    _record_security_event(db, request, "logout", True, user=current_user)
    db.commit()
    return {"ok": True}


@router.get("/auth/security-events")
def security_events(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(SecurityEvent).where(SecurityEvent.user_id == current_user.id).order_by(SecurityEvent.created_at.desc()).limit(100)).all()
    return {"events": [{"event_type": row.event_type, "success": row.success, "created_at": row.created_at, "user_agent": row.user_agent} for row in rows]}


@router.post("/auth/email-verification/request")
def request_email_verification(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.email_verified:
        return {"ok": True, "message": "Email is already verified", "delivery": "not_required"}
    if _account_action_is_limited(db, request, "email_verification_request", current_user.email):
        raise HTTPException(status_code=429, detail="Too many verification requests. Try again later.")
    _record_security_event(db, request, "email_verification_request", True, user=current_user, subject=current_user.email)
    settings = get_settings()
    raw_token = _create_account_token(db, current_user, AccountTokenPurpose.verify_email, timedelta(hours=settings.email_verification_hours))
    return _delivery_response(raw_token, AccountTokenPurpose.verify_email.value)


@router.post("/auth/email-verification/confirm")
def confirm_email_verification(payload: TokenActionRequest, db: Session = Depends(get_db)):
    token, user = _consume_account_token(db, payload.token, AccountTokenPurpose.verify_email)
    user.email_verified = True
    token.used_at = datetime.now(timezone.utc)
    db.commit()
    return {"ok": True, "email_verified": True}


@router.post("/auth/password-reset/request")
def request_password_reset(payload: EmailRequest, request: Request, db: Session = Depends(get_db)):
    email = payload.email.lower().strip()
    if _account_action_is_limited(db, request, "password_reset_request", email):
        return {"ok": True, "message": "If the account exists, instructions will be sent to its email address.", "delivery": "rate_limited"}
    user = db.scalar(select(User).where(User.email == email, User.is_active.is_(True)))
    _record_security_event(db, request, "password_reset_request", True, user=user, subject=email)
    if user is None:
        db.commit()
        return {"ok": True, "message": "If the account exists, instructions will be sent to its email address.", "delivery": "not_disclosed"}
    settings = get_settings()
    raw_token = _create_account_token(db, user, AccountTokenPurpose.reset_password, timedelta(minutes=settings.password_reset_minutes))
    return _delivery_response(raw_token, AccountTokenPurpose.reset_password.value)


@router.post("/auth/password-reset/confirm")
def confirm_password_reset(payload: PasswordResetConfirmRequest, db: Session = Depends(get_db)):
    token, user = _consume_account_token(db, payload.token, AccountTokenPurpose.reset_password)
    now = datetime.now(timezone.utc)
    user.password_hash = hash_password(payload.new_password)
    token.used_at = now
    db.execute(update(AccountActionToken).where(AccountActionToken.user_id == user.id, AccountActionToken.used_at.is_(None)).values(used_at=now))
    db.execute(update(UserSession).where(UserSession.user_id == user.id, UserSession.revoked_at.is_(None)).values(revoked_at=now))
    db.commit()
    return {"ok": True, "message": "Password has been updated"}


@router.get("/auth/me", response_model=AccountResponse)
def me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    membership = db.scalar(select(Membership).where(Membership.user_id == current_user.id))
    if membership is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Workspace membership is missing")
    workspace = db.get(Workspace, membership.workspace_id)
    subscription = db.scalar(select(Subscription).where(Subscription.workspace_id == membership.workspace_id).order_by(Subscription.created_at.desc()))
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
