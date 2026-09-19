from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.admin_router import _platform_overview
from app.db import Base
from app.models import BackgroundJob, JobStatus, MarketplaceConnection, Store, User, Workspace


AS_OF = datetime(2026, 9, 13, 12, 0, tzinfo=timezone.utc)


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine, autoflush=False)()


def _job(db, key, status, *, available_at=None, heartbeat_at=None, locked_at=None, finished_at=None):
    db.add(BackgroundJob(
        job_type="test.aggregate",
        idempotency_key=key,
        payload={"token": "must-not-leak", "customer": "private"},
        status=status,
        available_at=available_at or AS_OF,
        heartbeat_at=heartbeat_at,
        locked_at=locked_at,
        locked_by="secret-worker-name",
        last_error="secret provider error",
        finished_at=finished_at,
    ))


def test_empty_overview_reports_unknown_health_and_unavailable_business_metrics():
    _, db = _session()
    result = _platform_overview(db, as_of=AS_OF, lease_seconds=300)

    assert result["as_of"] == AS_OF
    assert result["users"] == {"total": 0, "enabled": 0, "new_7d": 0}
    assert result["operations"] == {"workspaces": 0, "active_stores": 0, "connections_saved": 0}
    assert result["jobs"]["backlog"] == {"ready": 0, "future_cooldown": 0, "oldest_ready_age_seconds": None}
    assert result["jobs"]["running_leases"] == {"fresh": 0, "stale": 0, "missing_timestamp": 0, "lease_seconds": 300}
    assert set(result["availability"].values()) == {None, "unknown"}
    assert "atomic snapshot" not in str(result).lower()


def test_overview_uses_exact_time_boundaries_available_at_and_effective_lease_timestamp():
    _, db = _session()
    stale_before = AS_OF - timedelta(seconds=300)
    _job(db, "ready-boundary", JobStatus.queued, available_at=AS_OF)
    _job(db, "cooldown", JobStatus.retry, available_at=AS_OF + timedelta(microseconds=1))
    _job(db, "fresh-boundary", JobStatus.running, locked_at=stale_before)
    _job(db, "fresh-heartbeat", JobStatus.running, locked_at=AS_OF - timedelta(hours=1), heartbeat_at=AS_OF)
    _job(db, "stale", JobStatus.running, heartbeat_at=stale_before - timedelta(microseconds=1))
    _job(db, "missing", JobStatus.running)
    _job(db, "success-boundary", JobStatus.succeeded, finished_at=AS_OF - timedelta(hours=24))
    _job(db, "success-old", JobStatus.succeeded, finished_at=AS_OF - timedelta(hours=24, microseconds=1))
    _job(db, "success-null", JobStatus.succeeded, finished_at=None)
    db.commit()

    result = _platform_overview(db, as_of=AS_OF, lease_seconds=300)

    assert result["jobs"]["queued"] == 1
    assert result["jobs"]["retry"] == 1
    assert result["jobs"]["running"] == 4
    assert result["jobs"]["succeeded_24h"] == 1
    assert result["jobs"]["backlog"] == {"ready": 1, "future_cooldown": 1, "oldest_ready_age_seconds": 0}
    assert result["jobs"]["running_leases"] == {"fresh": 2, "stale": 1, "missing_timestamp": 1, "lease_seconds": 300}


def test_overview_counts_only_source_backed_aggregates_and_never_exposes_row_data():
    _, db = _session()
    user = User(email="secret@example.com", password_hash="secret", full_name="Secret Customer", created_at=AS_OF - timedelta(days=7))
    disabled = User(email="old@example.com", password_hash="secret", is_active=False, created_at=AS_OF - timedelta(days=7, microseconds=1))
    workspace = Workspace(name="Secret Workspace")
    store = Store(workspace=workspace, name="Secret Store", is_active=True)
    db.add_all([user, disabled, workspace, store])
    db.flush()
    db.add(MarketplaceConnection(user_id=user.id, store_id=store.id, marketplace="wildberries", encrypted_token="top-secret"))
    _job(db, "old-dead", JobStatus.dead, available_at=AS_OF - timedelta(days=30))
    db.commit()

    result = _platform_overview(db, as_of=AS_OF, lease_seconds=300)

    assert result["users"] == {"total": 2, "enabled": 1, "new_7d": 1}
    assert result["operations"] == {"workspaces": 1, "active_stores": 1, "connections_saved": 1}
    assert result["jobs"]["dead"] == 1
    serialized = str(result)
    for secret in ["secret@example.com", "Secret Customer", "Secret Store", "secret-worker-name", "top-secret", "provider error"]:
        assert secret not in serialized


def test_overview_has_fixed_three_selects_and_performs_no_domain_writes():
    engine, db = _session()
    statements = []
    event.listen(engine, "before_cursor_execute", lambda conn, cursor, statement, parameters, context, executemany: statements.append(statement))

    _platform_overview(db, as_of=AS_OF, lease_seconds=300)

    assert len([sql for sql in statements if sql.lstrip().upper().startswith("SELECT")]) == 3
    assert not [sql for sql in statements if sql.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))]
    assert not db.new and not db.dirty and not db.deleted
