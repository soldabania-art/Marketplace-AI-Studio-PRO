from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db
from .models import User, UserMfa, UserSession

password_hash = PasswordHash.recommended()
bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return password_hash.verify(password, hashed)


def create_access_token(user_id: str, session_id: str) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "sid": session_id,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
        "type": "access",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def is_platform_admin(user: User) -> bool:
    return user.email.lower().strip() in get_settings().admin_email_set


def step_up_valid_until(session: UserSession) -> datetime | None:
    verified_at = session.step_up_verified_at
    if verified_at is None:
        return None
    if verified_at.tzinfo is None:
        verified_at = verified_at.replace(tzinfo=timezone.utc)
    return verified_at + timedelta(minutes=get_settings().step_up_minutes)


def _decode_access_token(token: str) -> tuple[str, str]:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        if payload.get("type") != "access":
            raise InvalidTokenError("wrong token type")
        user_id = payload.get("sub")
        session_id = payload.get("sid")
        if not user_id or not session_id:
            raise InvalidTokenError("missing token claims")
        return user_id, session_id
    except InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token") from exc


def get_current_session(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> UserSession:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    user_id, session_id = _decode_access_token(credentials.credentials)
    session = db.scalar(
        select(UserSession).where(
            UserSession.id == session_id,
            UserSession.user_id == user_id,
            UserSession.revoked_at.is_(None),
        )
    )
    if session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session is no longer active")
    expires_at = session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    if expires_at <= now:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session has expired")

    last_seen = session.last_seen_at
    if last_seen.tzinfo is None:
        last_seen = last_seen.replace(tzinfo=timezone.utc)
    write_interval = max(60, get_settings().session_last_seen_write_seconds)
    if (now - last_seen).total_seconds() >= write_interval:
        session.last_seen_at = now
        db.commit()
    return session


def require_step_up_session(current_session: UserSession = Depends(get_current_session)) -> UserSession:
    valid_until = step_up_valid_until(current_session)
    if valid_until is None or valid_until <= datetime.now(timezone.utc):
        raise HTTPException(
            status_code=428,
            detail="Подтвердите личность в разделе безопасности перед чувствительным действием",
        )
    return current_session


def get_current_user(
    current_session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
) -> User:
    user = db.scalar(select(User).where(User.id == current_session.user_id, User.is_active.is_(True)))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def require_platform_admin(current_session: UserSession = Depends(get_current_session), db: Session = Depends(get_db)) -> User:
    current_user = db.scalar(select(User).where(User.id == current_session.user_id, User.is_active.is_(True)))
    if current_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if not is_platform_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Platform administrator access required")
    mfa = db.get(UserMfa, current_user.id)
    if mfa is None or not mfa.enabled or current_session.mfa_verified_at is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Platform administrator MFA is required")
    return current_user


def require_platform_admin_step_up(
    current_user: User = Depends(require_platform_admin),
    _: UserSession = Depends(require_step_up_session),
) -> User:
    return current_user
