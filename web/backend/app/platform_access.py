from contextlib import contextmanager
from datetime import datetime, timezone
import threading

from fastapi import HTTPException, status
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from .models import PlatformStaffRole, PlatformStaffRoleName, User


PLATFORM_ACCESS_LOCK_KEY = 844_726_013
_sqlite_platform_access_lock = threading.RLock()

PROJECT_MANAGER_CAPABILITIES = ("platform.summary.read",)
OWNER_CAPABILITIES = (
    "platform.summary.read",
    "platform.users.read",
    "platform.jobs.read",
    "platform.team.manage",
    "platform.settings.write",
)


def get_effective_platform_role(db: Session, user_id: str) -> PlatformStaffRoleName | None:
    return db.scalar(
        select(PlatformStaffRole.role)
        .join(User, User.id == PlatformStaffRole.user_id)
        .where(
            PlatformStaffRole.user_id == user_id,
            PlatformStaffRole.revoked_at.is_(None),
            User.is_active.is_(True),
        )
        .execution_options(populate_existing=True)
    )


def platform_capabilities(role: PlatformStaffRoleName | None) -> list[str]:
    if role == PlatformStaffRoleName.owner:
        return list(OWNER_CAPABILITIES)
    if role == PlatformStaffRoleName.project_manager:
        return list(PROJECT_MANAGER_CAPABILITIES)
    return []


@contextmanager
def serialized_platform_access(db: Session):
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": PLATFORM_ACCESS_LOCK_KEY})
        yield
        return
    with _sqlite_platform_access_lock:
        yield


def require_effective_owner_after_lock(db: Session, actor_id: str) -> None:
    if get_effective_platform_role(db, actor_id) != PlatformStaffRoleName.owner:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Platform owner access required")


def _effective_owner_count(db: Session) -> int:
    return db.scalar(
        select(func.count())
        .select_from(PlatformStaffRole)
        .join(User, User.id == PlatformStaffRole.user_id)
        .where(
            PlatformStaffRole.role == PlatformStaffRoleName.owner,
            PlatformStaffRole.revoked_at.is_(None),
            User.is_active.is_(True),
        )
    ) or 0


def grant_project_manager(db: Session, *, actor_id: str, target_user_id: str) -> PlatformStaffRole:
    with serialized_platform_access(db):
        require_effective_owner_after_lock(db, actor_id)
        target = db.scalar(select(User).where(User.id == target_user_id).execution_options(populate_existing=True))
        if target is None:
            raise HTTPException(status_code=404, detail="User not found")
        if not target.is_active or not target.email_verified:
            raise HTTPException(status_code=422, detail="Target user must be active and email verified")
        existing = db.scalar(
            select(PlatformStaffRole)
            .where(PlatformStaffRole.user_id == target_user_id)
            .execution_options(populate_existing=True)
        )
        if existing is not None and existing.revoked_at is None:
            raise HTTPException(status_code=409, detail="User already has a platform role")
        now = datetime.now(timezone.utc)
        if existing is None:
            existing = PlatformStaffRole(
                user_id=target_user_id,
                role=PlatformStaffRoleName.project_manager,
                granted_by_user_id=actor_id,
                granted_at=now,
            )
            db.add(existing)
        else:
            existing.role = PlatformStaffRoleName.project_manager
            existing.granted_by_user_id = actor_id
            existing.granted_at = now
            existing.revoked_at = None
            existing.revoked_by_user_id = None
        db.flush()
        return existing


def revoke_platform_role(db: Session, *, actor_id: str, target_user_id: str) -> PlatformStaffRole:
    with serialized_platform_access(db):
        require_effective_owner_after_lock(db, actor_id)
        row = db.scalar(
            select(PlatformStaffRole)
            .where(PlatformStaffRole.user_id == target_user_id)
            .execution_options(populate_existing=True)
        )
        if row is None or row.revoked_at is not None:
            raise HTTPException(status_code=404, detail="Effective platform role not found")
        target_is_active = db.scalar(select(User.is_active).where(User.id == target_user_id))
        if row.role == PlatformStaffRoleName.owner and target_is_active and _effective_owner_count(db) <= 1:
            raise HTTPException(status_code=409, detail="The last effective platform owner cannot be revoked")
        row.revoked_at = datetime.now(timezone.utc)
        row.revoked_by_user_id = actor_id
        db.flush()
        return row


def set_user_active_serialized(db: Session, *, actor_id: str, target_user_id: str, active: bool) -> User:
    with serialized_platform_access(db):
        require_effective_owner_after_lock(db, actor_id)
        target = db.scalar(select(User).where(User.id == target_user_id).execution_options(populate_existing=True))
        if target is None:
            raise HTTPException(status_code=404, detail="User not found")
        role = db.scalar(
            select(PlatformStaffRole)
            .where(PlatformStaffRole.user_id == target_user_id)
            .execution_options(populate_existing=True)
        )
        if (
            not active
            and target.is_active
            and role is not None
            and role.revoked_at is None
            and role.role == PlatformStaffRoleName.owner
            and _effective_owner_count(db) <= 1
        ):
            raise HTTPException(status_code=409, detail="The last effective platform owner cannot be deactivated")
        target.is_active = active
        db.flush()
        return target
