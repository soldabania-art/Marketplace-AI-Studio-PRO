"""PostgreSQL session advisory leases bound to one checked-out connection."""
from __future__ import annotations

import hashlib
import logging
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Callable, Iterator

from sqlalchemy import event, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def advisory_key(name: str) -> int:
    raw = int.from_bytes(hashlib.blake2b(name.encode(), digest_size=8).digest(), "big")
    return raw if raw < 2**63 else raw - 2**64


@dataclass(frozen=True)
class AdvisoryLease:
    acquired: bool
    session: Session
    backend_pid: int | None


@contextmanager
def advisory_session_lease(session_factory: Callable[[], Session], name: str) -> Iterator[AdvisoryLease]:
    """Own a session lock and all transactions on one physical connection.

    Binding the ORM Session to an explicit Connection prevents commit/rollback
    from returning the locked connection to the pool. If the connection is lost,
    PostgreSQL releases its session locks when that backend disconnects.
    """
    probe = session_factory()
    bind = probe.get_bind()
    if bind.dialect.name != "postgresql":
        try:
            yield AdvisoryLease(True, probe, None)
        finally:
            probe.close()
        return
    probe.close()

    key = advisory_key(name)
    connection = bind.connect()
    db = Session(bind=connection, autoflush=False, autocommit=False, expire_on_commit=False)
    physical_connection = connection.connection.driver_connection

    def require_original_backend(conn, *args):
        # SQLAlchemy can transparently reconnect an invalidated Connection.
        # The replacement backend does not own this session-level lock.
        if conn.connection.driver_connection is not physical_connection:
            conn.invalidate()
            raise RuntimeError(f"PostgreSQL advisory lease was lost: {name}")

    event.listen(connection, "before_cursor_execute", require_original_backend)
    acquired = False
    backend_pid: int | None = None
    body_failed = False
    try:
        backend_pid = int(connection.execute(text("SELECT pg_backend_pid()")).scalar_one())
        acquired = bool(connection.execute(
            text("SELECT pg_try_advisory_lock(:key)"), {"key": key}
        ).scalar_one())
        # End the acquisition transaction while retaining the session-level
        # lock. The explicit Connection remains checked out, so later ORM
        # commit/rollback cycles cannot return it to the pool.
        connection.commit()
        yield AdvisoryLease(acquired, db, backend_pid)
    except BaseException:
        body_failed = True
        raise
    finally:
        try:
            if db.in_transaction():
                db.rollback()
            if acquired and connection.invalidated:
                if not body_failed:
                    raise RuntimeError(f"PostgreSQL advisory lease was lost: {name}")
            elif acquired:
                released = bool(connection.execute(
                    text("SELECT pg_advisory_unlock(:key)"), {"key": key}
                ).scalar_one())
                connection.commit()
                if not released:
                    connection.invalidate()
                    if not body_failed:
                        raise RuntimeError(f"PostgreSQL advisory lease was lost: {name}")
        except DBAPIError:
            connection.invalidate()
            if not body_failed:
                raise
            logger.exception("Failed to release advisory lease name=%s pid=%s", name, backend_pid)
        finally:
            event.remove(connection, "before_cursor_execute", require_original_backend)
            db.close()
            connection.close()
