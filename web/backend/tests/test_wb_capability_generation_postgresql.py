"""PostgreSQL-only WB01 fencing checks with independent DB sessions."""
from __future__ import annotations

from datetime import datetime, timezone
import uuid
import threading

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.db import SessionLocal, engine
from app.main import app
from app.marketplace_connections import _apply_capability_check, _claim_capability_check
from app.mfa_service import totp_code
from app.models import MarketplaceConnection, Store, User, Workspace


pytestmark = pytest.mark.skipif(
    engine.dialect.name != "postgresql",
    reason="WB capability concurrency acceptance requires PostgreSQL",
)


def _connection() -> str:
    suffix = uuid.uuid4().hex
    user_id = str(uuid.uuid4())
    workspace_id = str(uuid.uuid4())
    store_id = str(uuid.uuid4())
    connection_id = str(uuid.uuid4())
    with SessionLocal() as db:
        db.add(User(id=user_id, email=f"wb01-pg-{suffix}@example.com", password_hash="test"))
        db.add(Workspace(id=workspace_id, name=f"WB01 PG {suffix}"))
        db.flush()
        db.add(Store(id=store_id, workspace_id=workspace_id, name=f"Store {suffix}"))
        db.flush()
        db.add(MarketplaceConnection(
            id=connection_id,
            user_id=user_id,
            store_id=store_id,
            marketplace="wildberries",
            encrypted_token="encrypted-old",
            enabled=True,
            credentials_version=4,
            capability_check_generation=0,
        ))
        db.commit()
    return connection_id


def _result(marker: str) -> dict:
    return {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "summary": "complete",
        "probe_marker": marker,
        "sources": [],
    }


@pytest.mark.parametrize("concurrent_change", ["disconnect", "replace_credentials"])
def test_late_result_cannot_cross_concurrent_connection_change(concurrent_change):
    connection_id = _connection()
    with SessionLocal() as checking:
        stale = checking.get(MarketplaceConnection, connection_id)
        generation = _claim_capability_check(checking, stale, expected_version=4)
        checking_driver_connection = checking.connection().connection.driver_connection

        # This is a genuinely separate PostgreSQL transaction and connection.
        with SessionLocal() as changing:
            changing_driver_connection = changing.connection().connection.driver_connection
            assert changing_driver_connection is not checking_driver_connection
            current = changing.get(MarketplaceConnection, connection_id)
            if concurrent_change == "disconnect":
                current.enabled = False
                current.encrypted_token = ""
            else:
                current.encrypted_token = "encrypted-new"
            current.credentials_version += 1
            current.capability_check_generation += 1
            changing.commit()

        applied = _apply_capability_check(
            checking,
            connection_id=connection_id,
            expected_version=4,
            check_generation=generation,
            result=_result("stale"),
        )

    assert applied is False
    with SessionLocal() as verify:
        current = verify.get(MarketplaceConnection, connection_id)
        assert current.credentials_version == 5
        assert current.capability_results is None
        if concurrent_change == "disconnect":
            assert current.enabled is False
            assert current.encrypted_token == ""
        else:
            assert current.enabled is True
            assert current.encrypted_token == "encrypted-new"


def test_disconnect_endpoint_atomically_increments_after_concurrent_rotation(monkeypatch):
    """The DELETE must increment the committed version, not its stale ORM snapshot."""
    from app import marketplace_connections

    class Provider:
        def encrypt(self, value):
            return f"encrypted::{value}"

        def decrypt(self, value):
            return value.removeprefix("encrypted::")

    async def successful(_token):
        return _result("endpoint-rotation")

    monkeypatch.setattr(marketplace_connections, "secret_provider", lambda: Provider())
    monkeypatch.setattr(marketplace_connections, "check_wb_capabilities", successful)
    api = TestClient(app)
    password = "StrongPass123!"
    registered = api.post("/api/v1/auth/register", json={
        "email": f"wb01-pg-endpoint-{uuid.uuid4().hex}@example.com",
        "password": password,
        "workspace_name": "WB01 endpoint race",
    })
    headers = {"Authorization": f"Bearer {registered.json()['access_token']}"}
    store_id = api.get("/api/v1/stores", headers=headers).json()["stores"][0]["id"]
    setup = api.post("/api/v1/auth/mfa/setup", headers=headers, json={"password": password}).json()
    confirmed = api.post("/api/v1/auth/mfa/confirm", headers=headers, json={"code": totp_code(setup["secret"])})
    api.post("/api/v1/auth/step-up", headers=headers, json={
        "password": password,
        "code": confirmed.json()["recovery_codes"][0],
    })
    connection_id = _connection_for_store(store_id, api.get("/api/v1/auth/me", headers=headers).json()["id"])

    stale_loaded = threading.Event()
    allow_disconnect = threading.Event()

    def pause_stale_disconnect(_session, instance):
        if isinstance(instance, MarketplaceConnection) and not stale_loaded.is_set():
            stale_loaded.set()
            assert allow_disconnect.wait(10)

    event.listen(Session, "loaded_as_persistent", pause_stale_disconnect)
    result = {}

    def disconnect_request():
        result["response"] = api.delete(
            f"/api/v1/integrations/wildberries?store_id={store_id}", headers=headers,
        )

    worker = threading.Thread(target=disconnect_request, name="wb01-disconnect")
    try:
        worker.start()
        assert stale_loaded.wait(10)
        rotated = api.post("/api/v1/integrations/wildberries", headers=headers, json={
            "store_id": store_id,
            "token": "new-token-with-at-least-twenty-characters",
        })
        assert rotated.status_code == 200
        allow_disconnect.set()
        worker.join(10)
        assert not worker.is_alive()
        assert result["response"].status_code == 200
    finally:
        allow_disconnect.set()
        worker.join(10)
        event.remove(Session, "loaded_as_persistent", pause_stale_disconnect)

    with SessionLocal() as verify:
        current = verify.get(MarketplaceConnection, connection_id)
        assert current.credentials_version == 6
        assert current.capability_check_generation == 2
        assert current.enabled is False
        assert current.encrypted_token == ""


def _connection_for_store(store_id: str, user_id: str) -> str:
    connection_id = str(uuid.uuid4())
    with SessionLocal() as db:
        db.add(MarketplaceConnection(
            id=connection_id,
            user_id=user_id,
            store_id=store_id,
            marketplace="wildberries",
            encrypted_token="encrypted::old-token-with-at-least-twenty-characters",
            enabled=True,
            credentials_version=4,
            capability_check_generation=0,
        ))
        db.commit()
    return connection_id
