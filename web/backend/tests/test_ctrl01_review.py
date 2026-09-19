"""Independent review of transaction boundaries and stale staff authority."""
from datetime import datetime, timedelta, timezone
import uuid

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db import Base, get_db
from app.models import PlatformBootstrapState, PlatformStaffRole, PlatformStaffRoleName, User, UserMfa, UserSession
from app.bootstrap_platform_owners import bootstrap_platform_owners
from app.platform_access import grant_project_manager, revoke_platform_role
from app.security import create_access_token


@pytest.fixture
def staff_db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'staff-review.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, autoflush=False, expire_on_commit=False)
    with factory() as db:
        db.add_all([
            User(id=key, email=f"{key}@example.com", password_hash="not-used",
                 email_verified=True, is_active=True, full_name=key)
            for key in ("owner", "second-owner", "target", "unrelated")
        ])
        db.flush()
        db.add_all([
            PlatformStaffRole(user_id=key, role=PlatformStaffRoleName.owner)
            for key in ("owner", "second-owner")
        ])
        db.commit()
    yield factory
    engine.dispose()


def test_staff_grant_preserves_unrelated_pending_business_changes(staff_db):
    with staff_db() as db:
        db.get(User, "unrelated").full_name = "Pending business change"
        grant_project_manager(db, actor_id="owner", target_user_id="target")
        db.commit()
    with staff_db() as db:
        assert db.get(User, "unrelated").full_name == "Pending business change"
        assert db.get(PlatformStaffRole, "target").role == PlatformStaffRoleName.project_manager


def test_staff_grant_does_not_commit_callers_transaction(staff_db):
    with staff_db() as db:
        db.get(User, "unrelated").full_name = "Must roll back"
        grant_project_manager(db, actor_id="owner", target_user_id="target")
        # Session close rolls back both the role and the caller's business change.
    with staff_db() as db:
        assert db.get(PlatformStaffRole, "target") is None
        assert db.get(User, "unrelated").full_name == "unrelated"


@pytest.mark.parametrize("mutation", ["grant", "revoke"])
def test_loaded_owner_object_does_not_authorize_after_external_revocation(staff_db, mutation):
    with staff_db() as stale:
        loaded = stale.get(PlatformStaffRole, "owner")
        assert loaded.revoked_at is None
        with staff_db() as other:
            other.get(PlatformStaffRole, "owner").revoked_at = datetime.now(timezone.utc)
            other.commit()
        with pytest.raises(HTTPException) as rejected:
            if mutation == "grant":
                grant_project_manager(stale, actor_id="owner", target_user_id="target")
            else:
                revoke_platform_role(stale, actor_id="owner", target_user_id="second-owner")
        assert rejected.value.status_code == 403
    with staff_db() as db:
        assert db.get(PlatformStaffRole, "target") is None
        assert db.get(PlatformStaffRole, "second-owner").revoked_at is None


def test_bootstrap_cannot_resurrect_tombstone_even_without_marker(staff_db):
    with staff_db() as db:
        db.get(PlatformStaffRole, "owner").revoked_at = datetime.now(timezone.utc)
        db.commit()
        with pytest.raises(ValueError):
            bootstrap_platform_owners(db, {"owner@example.com"})
        assert db.scalar(select(PlatformBootstrapState)) is None
        assert db.get(PlatformStaffRole, "owner").revoked_at is not None


def test_bootstrap_is_atomic_with_callers_rollback(staff_db):
    with staff_db() as db:
        assert bootstrap_platform_owners(db, {"target@example.com"}) == 1
        assert db.get(PlatformStaffRole, "target") is not None
    with staff_db() as db:
        assert db.get(PlatformStaffRole, "target") is None
        assert db.scalar(select(PlatformBootstrapState)) is None


def test_inactive_owner_role_can_be_revoked_without_removing_last_active_owner(staff_db):
    with staff_db() as db:
        db.get(User, "second-owner").is_active = False
        db.commit()
        revoked = revoke_platform_role(db, actor_id="owner", target_user_id="second-owner")
        db.commit()
        assert revoked.revoked_at is not None
        assert db.get(PlatformStaffRole, "owner").revoked_at is None
        assert db.get(User, "owner").is_active is True


@pytest.fixture
def staff_client(staff_db):
    from app.main import app
    previous = dict(app.dependency_overrides)

    def database():
        with staff_db() as db:
            yield db

    app.dependency_overrides[get_db] = database
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


def _token(factory, user_id, *, mfa=True, step_up=True):
    now = datetime.now(timezone.utc)
    with factory() as db:
        session = UserSession(user_id=user_id, expires_at=now + timedelta(hours=1),
                              mfa_verified_at=now if mfa else None,
                              step_up_verified_at=now if step_up else None)
        db.add(session)
        if mfa:
            db.add(UserMfa(user_id=user_id, secret_ciphertext="unused", enabled=True,
                           recovery_code_hashes=[]))
        db.commit()
        return {"Authorization": f"Bearer {create_access_token(user_id, session.id)}"}


@pytest.mark.parametrize("method,path", [
    ("GET", "/admin/users"),
    ("GET", "/admin/jobs"),
    ("GET", "/admin/team"),
    ("GET", "/admin/knowledge"),
    ("GET", "/admin/fulfillment/partners"),
    ("PATCH", "/admin/users/target/status?active=false"),
    ("PATCH", "/admin/workspaces/missing/plan?plan_code=pro"),
    ("POST", "/admin/jobs/missing/requeue"),
    ("POST", "/admin/team/grants"),
    ("DELETE", "/admin/team/grants/second-owner"),
])
def test_manager_cannot_bypass_ui_via_owner_backend_endpoints(staff_db, staff_client, method, path):
    with staff_db() as db:
        db.get(PlatformStaffRole, "owner").role = PlatformStaffRoleName.project_manager
        db.commit()
    headers = _token(staff_db, "owner")
    kwargs = {"headers": headers}
    if path == "/admin/team/grants":
        kwargs["json"] = {"user_id": str(uuid.uuid4()), "role": "project_manager"}
    response = staff_client.request(method, "/api/v1" + path, **kwargs)
    assert response.status_code == 403, response.text


@pytest.mark.parametrize("mfa,step_up,expected", [(False, True, 403), (True, False, 428)])
def test_owner_mutations_still_require_mfa_and_step_up(staff_db, staff_client, mfa, step_up, expected):
    response = staff_client.patch("/api/v1/admin/users/target/status?active=false",
                                  headers=_token(staff_db, "owner", mfa=mfa, step_up=step_up))
    assert response.status_code == expected, response.text
    with staff_db() as db:
        assert db.get(User, "target").is_active is True


def test_allowlist_alone_does_not_grant_platform_access(staff_db, staff_client, monkeypatch):
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "admin_emails", "target@example.com")
    response = staff_client.get("/api/v1/admin/summary", headers=_token(staff_db, "target"))
    assert response.status_code == 403
