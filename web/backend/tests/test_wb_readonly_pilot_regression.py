"""One safe end-to-end WB read-only pilot regression, with no external network."""
from __future__ import annotations

import asyncio
import socket
import uuid
from datetime import date

import httpx
from fastapi.testclient import TestClient

from app import marketplace_connections, marketplace_sync, rate_limit
from app.db import Base, SessionLocal, engine
from app.job_queue import run_one
from app.main import app
from app.mfa_service import totp_code
from app.models import BackgroundJob, MarketplaceSnapshot
from app.wb_capability_preflight import check_wb_capabilities


Base.metadata.create_all(bind=engine)
client = TestClient(app)


class _TestSecrets:
    def encrypt(self, plaintext):
        return f"encrypted::{plaintext}"

    def decrypt(self, ciphertext):
        return ciphertext.removeprefix("encrypted::")


def _register_with_mfa():
    password = "StrongPass123!"
    registered = client.post("/api/v1/auth/register", json={
        "email": f"readonly-pilot-{uuid.uuid4().hex}@example.com",
        "password": password,
        "workspace_name": "Read-only WB pilot",
    })
    assert registered.status_code == 201
    headers = {"Authorization": f"Bearer {registered.json()['access_token']}"}
    setup = client.post("/api/v1/auth/mfa/setup", headers=headers, json={"password": password}).json()
    confirmed = client.post("/api/v1/auth/mfa/confirm", headers=headers, json={"code": totp_code(setup["secret"])})
    assert confirmed.status_code == 200
    stepped_up = client.post("/api/v1/auth/step-up", headers=headers, json={
        "password": password, "code": confirmed.json()["recovery_codes"][0],
    })
    assert stepped_up.status_code == 200
    store_id = client.get("/api/v1/stores", headers=headers).json()["stores"][0]["id"]
    return headers, store_id


def test_readonly_wb_pilot_preflight_enqueue_worker_snapshot_and_director(monkeypatch):
    """Partial WB access imports the independent core group and exposes honest diagnostics."""
    headers, store_id = _register_with_mfa()
    requests = []
    network_attempts = []
    stubbed_worker_calls = []
    original_socket_connect = socket.socket.connect

    async def no_wait(*args, **kwargs):
        return None

    def deny_external_socket_connect(sock, address):
        host = address[0] if isinstance(address, tuple) and address else ""
        if host in {"localhost", "127.0.0.1", "::1"}:
            return original_socket_connect(sock, address)
        network_attempts.append(address)
        raise AssertionError(f"external network is forbidden in this pilot test: {address}")

    def wb_stub(request):
        requests.append((request.method, request.url.host, request.url.path))
        assert request.url.host and request.url.host.endswith("wildberries.ru")
        if request.url.path == "/content/v2/get/cards/list":
            return httpx.Response(200, json={"cards": [{"nmID": 101}]})
        if request.url.path == "/api/analytics/v1/stocks-report/wb-warehouses":
            return httpx.Response(204)
        if request.url.path == "/api/analytics/v3/sales-funnel/products/history":
            return httpx.Response(200, json={"data": {"products": []}})
        if request.url.path == "/api/finance/v1/sales-reports/detailed":
            return httpx.Response(403, json={"detail": "denied"})
        if request.url.path == "/adv/v1/promotion/count":
            return httpx.Response(403, json={"detail": "denied"})
        if request.url.path == "/api/v1/feedbacks":
            return httpx.Response(200, json={"data": {"feedbacks": []}})
        raise AssertionError(f"unexpected WB request: {request.method} {request.url}")

    monkeypatch.setattr(rate_limit, "wait_marketplace_slot", no_wait)
    monkeypatch.setattr(socket.socket, "connect", deny_external_socket_connect)
    monkeypatch.setattr(marketplace_connections, "secret_provider", lambda: _TestSecrets())

    async def preflight(candidate):
        return await check_wb_capabilities(
            candidate,
            transport=httpx.MockTransport(wb_stub),
            today=date(2026, 9, 19),
        )

    monkeypatch.setattr(marketplace_connections, "check_wb_capabilities", preflight)
    connected = client.post("/api/v1/integrations/wildberries", headers=headers, json={
        "store_id": store_id, "token": "synthetic-readonly-token-123456", "accept_partial": True,
    })
    assert connected.status_code == 200
    verification = connected.json()["verification"]
    assert verification["summary"] == "partial"
    states = {row["key"]: row["status"] for row in verification["sources"]}
    assert states == {
        "catalog": "available", "analytics": "available", "finance": "forbidden",
        "advertising": "forbidden", "feedbacks": "available",
    }
    # The preflight owns the only HTTP transport in this scenario.  Its
    # MockTransport rejects every destination outside the WB contract above.
    assert network_attempts == []
    assert len(requests) == 6

    queued = client.post(f"/api/v1/onboarding/import?store_id={store_id}", headers=headers)
    assert queued.status_code == 202
    body = queued.json()
    assert set(body["jobs"]) == {"core"}
    assert body["skipped_groups"]["finance"]["state"] == "blocked"
    assert body["skipped_groups"]["advertising"]["state"] == "blocked"
    # This suite intentionally shares a database with unrelated queue tests.
    # Give only this synthetic job the first test-only priority so run_one claims it
    # without consuming another test's pending work.
    with SessionLocal() as db:
        db.get(BackgroundJob, body["jobs"]["core"]["id"]).priority = 0
        db.commit()

    async def cards(token):
        stubbed_worker_calls.append(("cards", token))
        return [{"nm_id": 101, "vendor_code": "SKU-101", "title": "Pilot product", "photo_count": 1}]

    async def stocks(token):
        stubbed_worker_calls.append(("stocks", token))
        return [{"nm_id": 101, "warehouse_id": 1, "warehouse_name": "WB", "quantity": 3}]

    async def sales(token, period_days=7):
        stubbed_worker_calls.append(("sales", token))
        return {101: {"nm_id": 101, "vendor_code": "SKU-101", "title": "Pilot product", "orders": 14,
                      "buyouts": 12, "period_days": period_days, "avg_daily_orders": 2}}

    monkeypatch.setattr(marketplace_sync, "fetch_wb_cards", cards)
    monkeypatch.setattr(marketplace_sync, "fetch_wb_current_stocks", stocks)
    monkeypatch.setattr(marketplace_sync, "fetch_wb_sales_velocity", sales)
    assert asyncio.run(run_one("readonly-pilot-worker", heartbeat_seconds=0.05)) is True
    assert network_attempts == []
    assert stubbed_worker_calls == [
        ("cards", "synthetic-readonly-token-123456"),
        ("stocks", "synthetic-readonly-token-123456"),
        ("sales", "synthetic-readonly-token-123456"),
    ]

    with SessionLocal() as db:
        job = db.get(BackgroundJob, body["jobs"]["core"]["id"])
        assert job.status.value == "succeeded"
        snapshots = db.query(MarketplaceSnapshot).filter_by(store_id=store_id).all()
        assert {row.snapshot_type for row in snapshots} == {"catalog", "stocks", "sales_velocity_7d"}

    director = client.get(f"/api/v1/director?store_id={store_id}", headers=headers)
    assert director.status_code == 200
    result = director.json()
    source_states = {source["name"]: source["state"] for source in result["sources"]}
    assert source_states["catalog"] == source_states["stocks"] == source_states["sales_velocity_7d"] == "live"
    assert source_states["finance_realization_sync"] == "missing"
    assert result["profit_status"] == "partial"
    assert result["summary"]["money_losses"]["observed_kopecks"] is None
    finance_action = next(action for action in result["actions"] if action["action_key"] == "source:finance_realization_sync")
    assert finance_action["can_execute"] is True
    assert finance_action["execution_type"] == "read_sync"
