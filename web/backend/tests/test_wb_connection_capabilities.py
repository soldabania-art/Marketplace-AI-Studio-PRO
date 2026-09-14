"""WB01 API regression tests for access gates and credential-generation fencing."""
from __future__ import annotations

import uuid
import asyncio
import threading
from datetime import datetime

from fastapi.testclient import TestClient

from app.db import Base, SessionLocal, engine
from app.main import app
from app.mfa_service import totp_code
from app.models import MarketplaceConnection, Membership, MembershipRole, Store


Base.metadata.create_all(bind=engine)
client = TestClient(app)


class FakeSecretProvider:
    def encrypt(self, plaintext):
        return f"encrypted::{plaintext}"

    def decrypt(self, ciphertext):
        return ciphertext.removeprefix("encrypted::")


def register():
    email = f"wb01-{uuid.uuid4().hex}@example.com"
    password = "StrongPass123!"
    response = client.post("/api/v1/auth/register", json={
        "email": email,
        "password": password,
        "workspace_name": "WB01 Store",
    })
    assert response.status_code == 201
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    store_id = client.get("/api/v1/stores", headers=headers).json()["stores"][0]["id"]
    return password, headers, store_id


def enable_mfa_and_step_up(password, headers):
    setup = client.post("/api/v1/auth/mfa/setup", headers=headers, json={"password": password}).json()
    confirmed = client.post(
        "/api/v1/auth/mfa/confirm",
        headers=headers,
        json={"code": totp_code(setup["secret"])},
    )
    assert confirmed.status_code == 200
    stepped = client.post(
        "/api/v1/auth/step-up",
        headers=headers,
        json={"password": password, "code": confirmed.json()["recovery_codes"][0]},
    )
    assert stepped.status_code == 200


def move_user_to_store_workspace(headers, store_id, role):
    user_id = client.get("/api/v1/auth/me", headers=headers).json()["id"]
    with SessionLocal() as db:
        store = db.get(Store, store_id)
        db.query(Membership).filter(Membership.user_id == user_id).delete()
        db.add(Membership(user_id=user_id, workspace_id=store.workspace_id, role=role))
        db.commit()


def full_result():
    return {
        "checked_at": "2026-09-13T12:00:00+00:00",
        "summary": "complete",
        "authentication_error": False,
        "requests_made": 7,
        "sources": [
            {"key": key, "label": key, "status": "available", "endpoints": [
                {"key": f"{key}.read", "status": "available", "authentication_error": False}
            ]}
            for key in ("catalog", "analytics", "finance", "advertising", "feedbacks")
        ],
    }


def test_unauthorized_missing_mfa_and_missing_step_up_stop_before_provider(monkeypatch):
    from app import marketplace_connections

    provider_calls = 0

    async def forbidden_provider(*args, **kwargs):
        nonlocal provider_calls
        provider_calls += 1
        return full_result()

    monkeypatch.setattr(marketplace_connections, "check_wb_capabilities", forbidden_provider)
    password, headers, store_id = register()
    body = {"store_id": store_id, "token": "x" * 40}

    assert client.post("/api/v1/integrations/wildberries", json=body).status_code == 401
    assert client.post("/api/v1/integrations/wildberries", headers=headers, json=body).status_code == 428
    assert client.post("/api/v1/auth/step-up", headers=headers, json={"password": password}).status_code == 200
    assert client.post("/api/v1/integrations/wildberries", headers=headers, json=body).status_code == 403
    assert provider_calls == 0


def test_foreign_store_is_rejected_before_provider(monkeypatch):
    from app import marketplace_connections

    provider_calls = 0

    async def forbidden_provider(*args, **kwargs):
        nonlocal provider_calls
        provider_calls += 1
        return full_result()

    monkeypatch.setattr(marketplace_connections, "check_wb_capabilities", forbidden_provider)
    password, headers, _ = register()
    _, _, foreign_store = register()
    enable_mfa_and_step_up(password, headers)
    response = client.post("/api/v1/integrations/wildberries", headers=headers, json={
        "store_id": foreign_store,
        "token": "x" * 40,
    })
    assert response.status_code == 404
    assert provider_calls == 0


def test_analyst_is_blocked_and_admin_is_allowed(monkeypatch):
    from app import marketplace_connections

    provider_calls = 0

    async def provider(*args, **kwargs):
        nonlocal provider_calls
        provider_calls += 1
        return full_result()

    monkeypatch.setattr(marketplace_connections, "check_wb_capabilities", provider)
    monkeypatch.setattr(marketplace_connections, "secret_provider", lambda: FakeSecretProvider())
    _, _, owner_store = register()

    analyst_password, analyst_headers, _ = register()
    move_user_to_store_workspace(analyst_headers, owner_store, MembershipRole.analyst)
    enable_mfa_and_step_up(analyst_password, analyst_headers)
    blocked = client.post("/api/v1/integrations/wildberries", headers=analyst_headers, json={
        "store_id": owner_store, "token": "analyst-token-must-not-be-used-123",
    })
    assert blocked.status_code == 403
    assert provider_calls == 0

    admin_password, admin_headers, _ = register()
    move_user_to_store_workspace(admin_headers, owner_store, MembershipRole.admin)
    enable_mfa_and_step_up(admin_password, admin_headers)
    allowed = client.post("/api/v1/integrations/wildberries", headers=admin_headers, json={
        "store_id": owner_store, "token": "admin-candidate-token-123456789",
    })
    assert allowed.status_code == 200
    assert provider_calls == 1


def test_existing_connection_starts_unchecked_and_full_candidate_is_versioned(monkeypatch):
    from app import marketplace_connections

    password, headers, store_id = register()
    enable_mfa_and_step_up(password, headers)
    monkeypatch.setattr(marketplace_connections, "secret_provider", lambda: FakeSecretProvider())
    monkeypatch.setattr(marketplace_connections, "check_wb_capabilities", lambda *args, **kwargs: None)

    initial = client.get(f"/api/v1/integrations/wildberries?store_id={store_id}", headers=headers)
    assert initial.json()["token_saved"] is False
    assert initial.json()["verification"]["summary"] == "unchecked"

    async def successful(*args, **kwargs):
        return full_result()

    monkeypatch.setattr(marketplace_connections, "check_wb_capabilities", successful)
    connected = client.post("/api/v1/integrations/wildberries", headers=headers, json={
        "store_id": store_id,
        "token": "new-candidate-token-1234567890",
    })
    assert connected.status_code == 200
    payload = connected.json()
    assert payload["connected"] is True
    assert payload["token_saved"] is True
    assert payload["sources_verified"] is True
    assert payload["credentials_version"] == 1
    assert "new-candidate-token" not in str(payload)


def test_existing_unverified_connection_is_not_invented_as_available(monkeypatch):
    from app import marketplace_connections

    _, headers, store_id = register()
    monkeypatch.setattr(marketplace_connections, "secret_provider", lambda: FakeSecretProvider())
    user_id = client.get("/api/v1/auth/me", headers=headers).json()["id"]
    with SessionLocal() as db:
        db.add(MarketplaceConnection(
            user_id=user_id,
            store_id=store_id,
            marketplace="wildberries",
            encrypted_token="encrypted::legacy-token",
            enabled=True,
            credentials_version=1,
            capability_results=None,
            capabilities_checked_at=None,
        ))
        db.commit()
    payload = client.get(f"/api/v1/integrations/wildberries?store_id={store_id}", headers=headers).json()
    assert payload["token_saved"] is True
    assert payload["sources_verified"] is False
    assert payload["verification"]["summary"] == "unchecked"
    assert {source["status"] for source in payload["verification"]["sources"]} == {"unchecked"}


def test_partial_candidate_requires_explicit_confirmation_and_preserves_working_token(monkeypatch):
    from app import marketplace_connections

    password, headers, store_id = register()
    enable_mfa_and_step_up(password, headers)
    monkeypatch.setattr(marketplace_connections, "secret_provider", lambda: FakeSecretProvider())
    result = full_result()
    result["summary"] = "partial"
    result["sources"][2]["status"] = "forbidden"
    result["sources"][2]["endpoints"][0]["status"] = "forbidden"

    async def partial(*args, **kwargs):
        return result

    monkeypatch.setattr(marketplace_connections, "check_wb_capabilities", partial)
    with SessionLocal() as db:
        db.add(MarketplaceConnection(
            user_id=client.get("/api/v1/auth/me", headers=headers).json()["id"],
            store_id=store_id,
            marketplace="wildberries",
            encrypted_token="encrypted::working-token",
            enabled=True,
            credentials_version=4,
        ))
        db.commit()

    rejected = client.post("/api/v1/integrations/wildberries", headers=headers, json={
        "store_id": store_id,
        "token": "partial-candidate-token-123456",
    })
    assert rejected.status_code == 409
    assert rejected.json()["detail"]["confirmation_required"] is True
    with SessionLocal() as db:
        row = db.query(MarketplaceConnection).filter_by(store_id=store_id).one()
        assert row.encrypted_token == "encrypted::working-token"
        assert row.credentials_version == 4

    accepted = client.post("/api/v1/integrations/wildberries", headers=headers, json={
        "store_id": store_id,
        "token": "partial-candidate-token-123456",
        "accept_partial": True,
    })
    assert accepted.status_code == 200
    assert accepted.json()["verification"]["summary"] == "partial"
    with SessionLocal() as db:
        row = db.query(MarketplaceConnection).filter_by(store_id=store_id).one()
        assert row.encrypted_token == "encrypted::partial-candidate-token-123456"
        assert row.credentials_version == 5


def test_transient_candidate_never_replaces_working_token(monkeypatch):
    from app import marketplace_connections

    password, headers, store_id = register()
    enable_mfa_and_step_up(password, headers)
    monkeypatch.setattr(marketplace_connections, "secret_provider", lambda: FakeSecretProvider())
    result = full_result()
    result["summary"] = "partial"
    result["sources"][0]["status"] = "transient_error"
    result["sources"][0]["endpoints"][0]["status"] = "transient_error"

    async def transient(*args, **kwargs):
        return result

    monkeypatch.setattr(marketplace_connections, "check_wb_capabilities", transient)
    user_id = client.get("/api/v1/auth/me", headers=headers).json()["id"]
    with SessionLocal() as db:
        db.add(MarketplaceConnection(
            user_id=user_id, store_id=store_id, marketplace="wildberries",
            encrypted_token="encrypted::working-token", enabled=True, credentials_version=2,
        ))
        db.commit()
    response = client.post("/api/v1/integrations/wildberries", headers=headers, json={
        "store_id": store_id,
        "token": "temporary-candidate-token-1234",
        "accept_partial": True,
    })
    assert response.status_code == 503
    with SessionLocal() as db:
        row = db.query(MarketplaceConnection).filter_by(store_id=store_id).one()
        assert row.encrypted_token == "encrypted::working-token"
        assert row.credentials_version == 2


def test_late_check_cannot_overwrite_new_credentials_or_reenable_disconnect(monkeypatch):
    from app import marketplace_connections

    password, headers, store_id = register()
    enable_mfa_and_step_up(password, headers)
    monkeypatch.setattr(marketplace_connections, "secret_provider", lambda: FakeSecretProvider())
    user_id = client.get("/api/v1/auth/me", headers=headers).json()["id"]
    with SessionLocal() as db:
        db.add(MarketplaceConnection(
            user_id=user_id, store_id=store_id, marketplace="wildberries",
            encrypted_token="encrypted::old-token", enabled=True, credentials_version=7,
        ))
        db.commit()

    async def rotate_during_check(*args, **kwargs):
        with SessionLocal() as other:
            row = other.query(MarketplaceConnection).filter_by(store_id=store_id).one()
            row.encrypted_token = "encrypted::new-token"
            row.credentials_version = 8
            row.capability_results = {"summary": "unchecked", "sources": []}
            other.commit()
        return full_result()

    monkeypatch.setattr(marketplace_connections, "check_wb_capabilities", rotate_during_check)
    stale = client.post(f"/api/v1/integrations/wildberries/check?store_id={store_id}", headers=headers)
    assert stale.status_code == 409
    with SessionLocal() as db:
        row = db.query(MarketplaceConnection).filter_by(store_id=store_id).one()
        assert row.credentials_version == 8
        assert row.capability_results["summary"] == "unchecked"

    async def disconnect_during_check(*args, **kwargs):
        with SessionLocal() as other:
            row = other.query(MarketplaceConnection).filter_by(store_id=store_id).one()
            row.enabled = False
            row.encrypted_token = ""
            row.credentials_version = 9
            other.commit()
        return full_result()

    monkeypatch.setattr(marketplace_connections, "check_wb_capabilities", disconnect_during_check)
    disconnected = client.post(f"/api/v1/integrations/wildberries/check?store_id={store_id}", headers=headers)
    assert disconnected.status_code in {409, 412}
    with SessionLocal() as db:
        row = db.query(MarketplaceConnection).filter_by(store_id=store_id).one()
        assert row.enabled is False
        assert row.credentials_version == 9


def test_acceptance_coefficients_success_does_not_claim_import_sources_ready(monkeypatch):
    """Reproduces the original contract bug without calling WB.

    A successful acceptance-coefficients read is useful for FBO, but it says
    nothing about catalog, analytics, finance, ads, or feedback permissions.
    """
    from app import router

    _, headers, store_id = register()
    user_id = client.get("/api/v1/auth/me", headers=headers).json()["id"]
    rejected_sources = full_result()
    rejected_sources["summary"] = "rejected"
    for source in rejected_sources["sources"]:
        source["status"] = "forbidden"
        for endpoint in source["endpoints"]:
            endpoint["status"] = "forbidden"
    with SessionLocal() as db:
        db.add(MarketplaceConnection(
            user_id=user_id,
            store_id=store_id,
            marketplace="wildberries",
            encrypted_token="encrypted::acceptance-only-token",
            enabled=True,
            credentials_version=1,
            capability_results=rejected_sources,
            capabilities_checked_at=datetime.fromisoformat(rejected_sources["checked_at"]),
        ))
        db.commit()

    async def acceptance_coefficients_are_available(*args, **kwargs):
        return [{"warehouse_id": 1, "warehouse_name": "Mock", "coefficient": 0, "free_acceptance": True}]

    monkeypatch.setattr(router, "fetch_wb_slots", acceptance_coefficients_are_available)
    monkeypatch.setattr(router, "decrypt_connection", lambda row: "acceptance-only-token")
    slots = client.get(f"/api/v1/fbo/slots?store_id={store_id}", headers=headers)
    status = client.get(f"/api/v1/integrations/wildberries?store_id={store_id}", headers=headers)

    assert slots.status_code == 200
    assert slots.json()["slots"][0]["free_acceptance"] is True
    assert status.json()["token_saved"] is True
    assert status.json()["sources_verified"] is True
    assert status.json()["verification"]["summary"] == "rejected"
    assert all(
        source["status"] == "forbidden"
        for source in status.json()["verification"]["sources"]
    )


def test_two_checks_same_credentials_apply_only_latest_generation(monkeypatch):
    from app import marketplace_connections

    password, headers, store_id = register()
    enable_mfa_and_step_up(password, headers)
    monkeypatch.setattr(marketplace_connections, "secret_provider", lambda: FakeSecretProvider())
    user_id = client.get("/api/v1/auth/me", headers=headers).json()["id"]
    with SessionLocal() as db:
        db.add(MarketplaceConnection(
            user_id=user_id, store_id=store_id, marketplace="wildberries",
            encrypted_token="encrypted::same-token", enabled=True, credentials_version=3,
        ))
        db.commit()

    first_started = threading.Event()
    release_first = threading.Event()
    call_lock = threading.Lock()
    call_number = 0

    async def controlled_check(*args, **kwargs):
        nonlocal call_number
        with call_lock:
            call_number += 1
            mine = call_number
        result = full_result()
        result["checked_at"] = f"2026-09-13T12:00:0{mine}+00:00"
        result["probe_marker"] = f"check-{mine}"
        if mine == 1:
            first_started.set()
            await asyncio.to_thread(release_first.wait, 5)
        return result

    monkeypatch.setattr(marketplace_connections, "check_wb_capabilities", controlled_check)
    responses = {}

    def run(name):
        responses[name] = client.post(
            f"/api/v1/integrations/wildberries/check?store_id={store_id}", headers=headers,
        )

    old = threading.Thread(target=run, args=("old",))
    new = threading.Thread(target=run, args=("new",))
    old.start()
    assert first_started.wait(3)
    new.start()
    new.join(5)
    assert not new.is_alive()
    release_first.set()
    old.join(5)

    assert responses["new"].status_code == 200
    assert responses["old"].status_code == 409
    with SessionLocal() as db:
        row = db.query(MarketplaceConnection).filter_by(store_id=store_id).one()
        assert row.credentials_version == 3
        assert row.capability_results["probe_marker"] == "check-2"
