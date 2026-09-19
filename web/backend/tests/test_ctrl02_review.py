"""Independent boundary and authorization review for the platform overview."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.admin_router import _platform_overview
from app.db import Base, SessionLocal, engine as application_engine, get_db
from app.models import (
    BackgroundJob, JobStatus, MarketplaceConnection, Membership, MembershipRole,
    PlatformStaffRole, PlatformStaffRoleName, Store, User, UserMfa, UserSession, Workspace,
)
from app.security import create_access_token


NOW = datetime(2026, 9, 13, 12, tzinfo=timezone.utc)


@pytest.fixture
def database(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'overview-review.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, autoflush=False, expire_on_commit=False)
    yield factory
    engine.dispose()


def job(key, state, **values):
    return BackgroundJob(job_type="private.operation", idempotency_key=key, status=state,
                         payload={"token": "SECRET-PAYLOAD"}, last_error="SECRET-ERROR",
                         locked_by="SECRET-WORKER", **values)


def test_future_timestamps_do_not_inflate_recent_activity(database):
    with database() as db:
        db.add_all([
            User(email=f"u{n}@example.com", password_hash="unused", created_at=when)
            for n, when in enumerate([NOW, NOW + timedelta(microseconds=1), NOW - timedelta(days=7, microseconds=1)])
        ])
        db.add_all([
            job("now", JobStatus.succeeded, finished_at=NOW),
            job("future", JobStatus.succeeded, finished_at=NOW + timedelta(microseconds=1)),
            job("old", JobStatus.succeeded, finished_at=NOW - timedelta(hours=24, microseconds=1)),
        ])
        db.commit()
        result = _platform_overview(db, as_of=NOW, lease_seconds=300)
    assert result["users"]["new_7d"] == 1
    assert result["jobs"]["succeeded_24h"] == 1
    assert result["windows"]["new_users_until"] == NOW
    assert result["windows"]["succeeded_jobs_until"] == NOW


def test_ready_age_excludes_creation_time_and_future_retries(database):
    with database() as db:
        db.add_all([
            job("ready", JobStatus.queued, created_at=NOW - timedelta(days=90), available_at=NOW - timedelta(seconds=42)),
            job("future", JobStatus.retry, created_at=NOW - timedelta(days=120), available_at=NOW + timedelta(hours=6)),
        ])
        db.commit()
        result = _platform_overview(db, as_of=NOW, lease_seconds=300)
    assert result["jobs"]["backlog"] == {"ready": 1, "future_cooldown": 1, "oldest_ready_age_seconds": 42}


def test_saved_connections_exclude_inactive_disabled_other_marketplace_and_legacy(database):
    with database() as db:
        user = User(email="secret@example.com", password_hash="unused")
        workspace = Workspace(name="SECRET-WORKSPACE")
        db.add_all([user, workspace])
        db.flush()
        for n, (active, marketplace, enabled) in enumerate([
            (True, "wildberries", True), (False, "wildberries", True),
            (True, "wildberries", False), (True, "ozon", True),
        ]):
            store = Store(workspace_id=workspace.id, name=f"SECRET-STORE-{n}", is_active=active)
            db.add(store)
            db.flush()
            db.add(MarketplaceConnection(user_id=user.id, store_id=store.id, marketplace=marketplace,
                                         enabled=enabled, encrypted_token="SECRET-TOKEN"))
        db.add(MarketplaceConnection(user_id=user.id, store_id=None, marketplace="wildberries",
                                     enabled=True, encrypted_token="SECRET-LEGACY-TOKEN"))
        db.commit()
        result = _platform_overview(db, as_of=NOW, lease_seconds=300)
    assert result["operations"] == {"workspaces": 1, "active_stores": 3, "connections_saved": 1}
    assert "SECRET" not in str(result)
    assert "secret@example.com" not in str(result)


def test_heartbeat_precedes_locked_at_and_scheduled_only_has_no_ready_age(database):
    with database() as db:
        db.add_all([
            job("stale-heartbeat", JobStatus.running, heartbeat_at=NOW - timedelta(seconds=301), locked_at=NOW),
            job("missing", JobStatus.running),
            job("scheduled", JobStatus.retry, available_at=NOW + timedelta(minutes=1)),
        ])
        db.commit()
        result = _platform_overview(db, as_of=NOW, lease_seconds=300)
    assert result["jobs"]["running_leases"] == {"fresh": 0, "stale": 1, "missing_timestamp": 1, "lease_seconds": 300}
    assert result["jobs"]["backlog"]["oldest_ready_age_seconds"] is None
    assert result["availability"]["worker_health"] == "unknown"
    assert "SECRET" not in str(result)


@pytest.fixture
def client(database):
    from app.main import app
    previous = dict(app.dependency_overrides)

    def db_dependency():
        with database() as db:
            yield db

    app.dependency_overrides[get_db] = db_dependency
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


def staff(factory, role, *, mfa=True):
    now = datetime.now(timezone.utc)
    with factory() as db:
        user = User(email="staff@example.com", password_hash="unused", email_verified=True)
        db.add(user)
        db.flush()
        if role == "tenant_owner":
            workspace = Workspace(name="Private tenant")
            db.add(workspace)
            db.flush()
            db.add(Membership(user_id=user.id, workspace_id=workspace.id, role=MembershipRole.owner))
        else:
            db.add(PlatformStaffRole(user_id=user.id, role=PlatformStaffRoleName(role)))
        session = UserSession(user_id=user.id, expires_at=now + timedelta(hours=1),
                              mfa_verified_at=now if mfa else None)
        db.add(session)
        if mfa:
            db.add(UserMfa(user_id=user.id, secret_ciphertext="unused", enabled=True, recovery_code_hashes=[]))
        db.commit()
        return user.id, {"Authorization": f"Bearer {create_access_token(user.id, session.id)}"}


@pytest.mark.parametrize("role,mfa,expected", [
    ("guest", False, 401), ("tenant_owner", True, 403), ("owner", False, 403),
    ("owner", True, 200), ("project_manager", True, 200),
])
def test_overview_endpoint_preserves_staff_and_mfa_boundary(database, client, role, mfa, expected):
    headers = {} if role == "guest" else staff(database, role, mfa=mfa)[1]
    response = client.get("/api/v1/admin/overview", headers=headers)
    assert response.status_code == expected, response.text
    if expected == 200:
        assert response.json()["access"]["scope"] == "platform_aggregate"
        assert "staff@example.com" not in response.text
        assert response.json()["availability"]["confirmed_revenue"] is None


def test_same_session_loses_overview_after_role_revocation(database, client):
    user_id, headers = staff(database, "project_manager")
    assert client.get("/api/v1/admin/overview", headers=headers).status_code == 200
    with database() as db:
        db.get(PlatformStaffRole, user_id).revoked_at = datetime.now(timezone.utc)
        db.commit()
    assert client.get("/api/v1/admin/overview", headers=headers).status_code == 403


@pytest.mark.skipif(application_engine.dialect.name != "postgresql", reason="runs aggregate SQL on PostgreSQL in CI")
def test_overview_aggregate_sql_executes_on_postgresql():
    as_of = datetime.now(timezone.utc)
    with SessionLocal() as db:
        baseline = _platform_overview(db, as_of=as_of, lease_seconds=300)
        db.add(User(email=f"ctrl02-pg-{as_of.timestamp()}@example.com", password_hash="unused", created_at=as_of))
        db.add(job(f"ctrl02-pg-{as_of.timestamp()}", JobStatus.queued, available_at=as_of))
        db.flush()
        result = _platform_overview(db, as_of=as_of, lease_seconds=300)
        db.rollback()

    assert result["users"]["total"] == baseline["users"]["total"] + 1
    assert result["jobs"]["queued"] == baseline["jobs"]["queued"] + 1
    assert result["jobs"]["backlog"]["ready"] == baseline["jobs"]["backlog"]["ready"] + 1
    assert all(isinstance(result["jobs"][key], int) for key in ("queued", "running", "retry", "dead", "succeeded_24h"))
