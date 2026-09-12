"""T08C regression coverage for session advisory-lock connection ownership."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from app.db import SessionLocal, engine


def _try_lock(connection, key: int) -> bool:
    return bool(connection.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": key}).scalar())


def _unlock(connection, key: int) -> None:
    connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": key})


@pytest.mark.skipif(engine.dialect.name != "postgresql", reason="physical PostgreSQL connections")
@pytest.mark.parametrize("transaction_end", ["commit", "rollback"])
def test_session_advisory_lease_keeps_physical_connection_across_transaction_end(transaction_end):
    from app.advisory_lock import advisory_key, advisory_session_lease

    name = f"t08c:transaction:{uuid.uuid4().hex}"
    key = advisory_key(name)
    with advisory_session_lease(SessionLocal, name) as lease:
        assert lease.acquired is True
        owner_pid = lease.backend_pid
        getattr(lease.session, transaction_end)()

        with engine.connect() as contender:
            contender_pid = contender.execute(text("SELECT pg_backend_pid()")).scalar_one()
            assert contender_pid != owner_pid, "the leased connection was returned to the pool"
            assert _try_lock(contender, key) is False

    with engine.connect() as successor:
        assert _try_lock(successor, key) is True
        _unlock(successor, key)


@pytest.mark.skipif(engine.dialect.name != "postgresql", reason="physical PostgreSQL connections")
def test_session_advisory_lease_releases_after_exception_without_pool_leak():
    from app.advisory_lock import advisory_key, advisory_session_lease

    name = f"t08c:exception:{uuid.uuid4().hex}"
    key = advisory_key(name)
    with pytest.raises(RuntimeError, match="injected failure"):
        with advisory_session_lease(SessionLocal, name) as lease:
            assert lease.acquired is True
            lease.session.commit()
            raise RuntimeError("injected failure")

    with engine.connect() as reused:
        assert _try_lock(reused, key) is True
        _unlock(reused, key)
