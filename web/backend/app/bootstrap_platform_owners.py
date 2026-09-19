import sys

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import get_settings
from .db import SessionLocal
from .models import PlatformBootstrapState, PlatformStaffRole, PlatformStaffRoleName, User
from .platform_access import serialized_platform_access


BOOTSTRAP_KEY = "admin_emails_v1"


def bootstrap_platform_owners(db: Session, configured_emails: set[str]) -> int:
    emails = {value.strip().lower() for value in configured_emails if value.strip()}
    with serialized_platform_access(db):
        if db.get(PlatformBootstrapState, BOOTSTRAP_KEY) is not None:
            return 0
        if not emails:
            raise ValueError("ADMIN_EMAILS must contain at least one address for initial bootstrap")
        users = list(db.scalars(select(User).where(func.lower(User.email).in_(emails))).all())
        by_email = {user.email.strip().lower(): user for user in users}
        invalid = sorted(
            email for email in emails
            if email not in by_email or not by_email[email].is_active or not by_email[email].email_verified
        )
        if invalid:
            raise ValueError("Every bootstrap owner must be an existing active verified user: " + ", ".join(invalid))
        existing = list(db.scalars(select(PlatformStaffRole).where(
            PlatformStaffRole.user_id.in_([user.id for user in users])
        )).all())
        if existing:
            raise ValueError("Bootstrap refuses to overwrite existing or revoked platform roles")
        for user in users:
            db.add(PlatformStaffRole(user_id=user.id, role=PlatformStaffRoleName.owner))
        db.add(PlatformBootstrapState(
            key=BOOTSTRAP_KEY,
            details={"source": "ADMIN_EMAILS", "owner_count": len(users)},
        ))
        db.flush()
        return len(users)


def main() -> int:
    with SessionLocal() as db:
        try:
            count = bootstrap_platform_owners(db, get_settings().admin_email_set)
            db.commit()
        except Exception as exc:
            db.rollback()
            print(f"Platform owner bootstrap failed: {exc}", file=sys.stderr)
            return 1
    print(f"Platform owner bootstrap complete; owners granted: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
