from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.bootstrap_platform_owners import bootstrap_platform_owners
from app.db import Base, SessionLocal, engine
from app.main import app
from app.models import (
    PlatformBootstrapState,
    PlatformStaffRole,
    PlatformStaffRoleName,
    SecurityEvent,
    Subscription,
    User,
    UserMfa,
    UserSession,
)
from app.platform_access import get_effective_platform_role, revoke_platform_role, set_user_active_serialized


Base.metadata.create_all(bind=engine)
client = TestClient(app)


@pytest.fixture(autouse=True)
def _isolate_platform_access_rows():
    with SessionLocal() as db:
        db.query(PlatformStaffRole).delete()
        db.query(PlatformBootstrapState).delete()
        db.commit()
    yield
    with SessionLocal() as db:
        db.query(PlatformStaffRole).delete()
        db.query(PlatformBootstrapState).delete()
        db.commit()


def _account(*, verified=True, role=None, mfa=True, step_up=True):
    email = f"platform-{uuid.uuid4().hex}@example.com"
    password = "StrongPass123!"
    registered = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "workspace_name": "Platform test"},
    )
    assert registered.status_code == 201
    token = registered.json()["access_token"]
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email))
        user.email_verified = verified
        session = db.scalar(
            select(UserSession)
            .where(UserSession.user_id == user.id, UserSession.revoked_at.is_(None))
            .order_by(UserSession.created_at.desc())
        )
        if mfa:
            db.add(UserMfa(user_id=user.id, secret_ciphertext="test", enabled=True, recovery_code_hashes=[]))
            session.mfa_verified_at = datetime.now(timezone.utc)
        if step_up:
            session.step_up_verified_at = datetime.now(timezone.utc)
        if role:
            db.add(PlatformStaffRole(user_id=user.id, role=role))
        db.commit()
        return user.id, email, token


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_project_manager_has_only_safe_aggregate_read_capability():
    _, _, token = _account(role=PlatformStaffRoleName.project_manager)
    headers = _headers(token)

    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["platform_role"] == "project_manager"
    assert me.json()["platform_capabilities"] == ["platform.summary.read"]

    summary = client.get("/api/v1/admin/summary", headers=headers)
    assert summary.status_code == 200
    assert set(summary.json()) == {
        "users", "active_users", "workspaces", "active_subscriptions", "trial_subscriptions"
    }
    assert client.get("/api/v1/admin/users", headers=headers).status_code == 403
    assert client.get("/api/v1/admin/jobs", headers=headers).status_code == 403
    assert client.get("/api/v1/admin/team", headers=headers).status_code == 403
    assert client.patch("/api/v1/admin/workspaces/missing/plan?plan_code=pro", headers=headers).status_code == 403


def test_owner_grants_and_revokes_only_project_manager_for_verified_existing_user():
    owner_id, _, owner_token = _account(role=PlatformStaffRoleName.owner)
    target_id, _, target_token = _account(verified=False)
    headers = _headers(owner_token)

    rejected = client.post(
        "/api/v1/admin/team/grants",
        headers=headers,
        json={"user_id": target_id, "role": "project_manager"},
    )
    assert rejected.status_code == 422
    with SessionLocal() as db:
        db.get(User, target_id).email_verified = True
        db.commit()

    assert client.post(
        "/api/v1/admin/team/grants",
        headers=headers,
        json={"user_id": target_id, "role": "owner"},
    ).status_code == 422
    granted = client.post(
        "/api/v1/admin/team/grants",
        headers=headers,
        json={"user_id": target_id, "role": "project_manager"},
    )
    assert granted.status_code == 201
    assert client.get("/api/v1/admin/summary", headers=_headers(target_token)).status_code == 200

    revoked = client.delete(f"/api/v1/admin/team/grants/{target_id}", headers=headers)
    assert revoked.status_code == 200
    assert client.get("/api/v1/admin/summary", headers=_headers(target_token)).status_code == 403
    with SessionLocal() as db:
        kinds = set(db.scalars(select(SecurityEvent.event_type).where(SecurityEvent.user_id == owner_id)).all())
        assert {"platform_staff.granted", "platform_staff.revoked"} <= kinds


def test_last_effective_owner_cannot_be_revoked_or_deactivated_and_mutations_are_audited():
    owner_id, _, token = _account(role=PlatformStaffRoleName.owner)
    headers = _headers(token)
    assert client.delete(f"/api/v1/admin/team/grants/{owner_id}", headers=headers).status_code == 409
    assert client.patch(
        f"/api/v1/admin/users/{owner_id}/status?active=false", headers=headers
    ).status_code == 409

    with SessionLocal() as db:
        subscription = db.scalar(select(Subscription).limit(1))
        workspace_id = subscription.workspace_id
    changed = client.patch(
        f"/api/v1/admin/workspaces/{workspace_id}/plan?plan_code=pro", headers=headers
    )
    assert changed.status_code == 200
    with SessionLocal() as db:
        assert db.scalar(select(SecurityEvent).where(
            SecurityEvent.user_id == owner_id,
            SecurityEvent.event_type == "admin_workspace_plan_changed",
        )) is not None


def test_admin_emails_bootstrap_is_explicit_atomic_and_never_resurrects_revoked_role():
    first_id, first_email, _ = _account(verified=True)
    _, invalid_email, _ = _account(verified=False)
    with SessionLocal() as db:
        with pytest.raises(ValueError):
            bootstrap_platform_owners(db, {first_email, invalid_email})
        assert db.get(PlatformBootstrapState, "admin_emails_v1") is None
        assert db.get(PlatformStaffRole, first_id) is None

        db.get(User, db.scalar(select(User.id).where(User.email == invalid_email))).email_verified = True
        assert bootstrap_platform_owners(db, {first_email, invalid_email}) == 2
        role = db.get(PlatformStaffRole, first_id)
        role.revoked_at = datetime.now(timezone.utc)
        db.commit()
        assert bootstrap_platform_owners(db, {first_email, invalid_email}) == 0
        db.refresh(role)
        assert role.revoked_at is not None


def test_empty_or_previously_revoked_bootstrap_configuration_does_not_mark_complete():
    user_id, email, _ = _account(verified=True)
    with SessionLocal() as db:
        with pytest.raises(ValueError):
            bootstrap_platform_owners(db, set())
        assert db.get(PlatformBootstrapState, "admin_emails_v1") is None
        db.add(PlatformStaffRole(
            user_id=user_id,
            role=PlatformStaffRoleName.owner,
            revoked_at=datetime.now(timezone.utc),
        ))
        db.commit()
        with pytest.raises(ValueError):
            bootstrap_platform_owners(db, {email})
        assert db.get(PlatformBootstrapState, "admin_emails_v1") is None


@pytest.mark.skipif(engine.dialect.name != "postgresql", reason="requires PostgreSQL locking semantics")
@pytest.mark.parametrize("first_operation,second_operation", [
    ("revoke", "revoke"),
    ("deactivate", "deactivate"),
    ("revoke", "deactivate"),
])
def test_concurrent_owner_removals_preserve_an_effective_owner(first_operation, second_operation):
    first_id, _, _ = _account(role=PlatformStaffRoleName.owner)
    second_id, _, _ = _account(role=PlatformStaffRoleName.owner)
    ready = __import__("threading").Barrier(2)

    def remove_access(actor_id, target_id, operation):
        with SessionLocal() as db:
            pid = db.scalar(select(func.pg_backend_pid()))
            assert get_effective_platform_role(db, actor_id) == PlatformStaffRoleName.owner
            ready.wait(timeout=10)
            try:
                if operation == "revoke":
                    revoke_platform_role(db, actor_id=actor_id, target_user_id=target_id)
                else:
                    set_user_active_serialized(db, actor_id=actor_id, target_user_id=target_id, active=False)
                db.commit()
                return pid, "changed"
            except Exception as exc:
                db.rollback()
                return pid, getattr(exc, "status_code", type(exc).__name__)

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = [
            future.result()
            for future in (
                pool.submit(remove_access, first_id, second_id, first_operation),
                pool.submit(remove_access, second_id, first_id, second_operation),
            )
        ]

    assert len({pid for pid, _ in outcomes}) == 2
    assert sorted((result for _, result in outcomes), key=str) == [403, "changed"]
    with SessionLocal() as db:
        effective_owners = db.scalar(
            select(func.count())
            .select_from(PlatformStaffRole)
            .join(User, User.id == PlatformStaffRole.user_id)
            .where(
                PlatformStaffRole.role == PlatformStaffRoleName.owner,
                PlatformStaffRole.revoked_at.is_(None),
                User.is_active.is_(True),
            )
        )
        assert effective_owners >= 1
