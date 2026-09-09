import uuid

from fastapi.testclient import TestClient

from app.db import Base, engine
from app.main import app

Base.metadata.create_all(bind=engine)
client = TestClient(app)


def _account():
    email = f"agent-{uuid.uuid4().hex}@example.com"
    response = client.post("/api/v1/auth/register", json={"email": email, "password": "StrongPass123!", "workspace_name": "Agent Test"})
    assert response.status_code == 201
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    store_id = client.get("/api/v1/stores", headers=headers).json()["stores"][0]["id"]
    return headers, store_id


def test_network_is_store_scoped_and_feedback_does_not_auto_train():
    first_headers, first_store = _account()
    second_headers, second_store = _account()

    network = client.get(f"/api/v1/agents/network?store_id={first_store}", headers=first_headers)
    assert network.status_code == 200
    assert network.json()["master_agent"] == "director"
    assert network.json()["control"]["platform_policy_can_override_security_denial"] is False

    forbidden = client.get(f"/api/v1/agents/network?store_id={second_store}", headers=first_headers)
    assert forbidden.status_code == 404

    created = client.post("/api/v1/agents/learning", headers=first_headers, json={
        "store_id": first_store,
        "agent_key": "finance",
        "signal": "incorrect",
        "source_type": "manual",
        "note": "Проверь расчёт. Bearer abcdefghijklmnopqrstuvwxyz user@example.com",
    })
    assert created.status_code == 201
    body = created.json()
    assert body["status"] == "candidate"
    assert body["promotion_applied"] is False
    assert "Bearer" not in body["note"]
    assert "user@example.com" not in body["note"]

    duplicate = client.post("/api/v1/agents/learning", headers=first_headers, json={
        "store_id": first_store,
        "agent_key": "finance",
        "signal": "incorrect",
        "source_type": "manual",
        "note": "Проверь расчёт. Bearer abcdefghijklmnopqrstuvwxyz user@example.com",
    })
    assert duplicate.status_code == 201
    assert duplicate.json()["id"] == body["id"]

    listed = client.get(f"/api/v1/agents/learning?store_id={first_store}", headers=first_headers)
    assert listed.status_code == 200
    assert listed.json()["auto_training"] is False
    assert listed.json()["items"][0]["id"] == body["id"]


def test_unknown_agent_cannot_create_learning_candidate():
    headers, store_id = _account()
    response = client.post("/api/v1/agents/learning", headers=headers, json={
        "store_id": store_id,
        "agent_key": "unregistered",
        "signal": "helpful",
    })
    assert response.status_code == 404


def test_director_routes_idempotent_work_order_without_execution():
    headers, store_id = _account()
    payload = {
        "store_id": store_id,
        "goal_type": "profit_review",
        "subject_id": "nm-123",
        "instruction": "Проверь прибыль user@example.com и не меняй цену",
    }
    created = client.post("/api/v1/agents/work-orders", headers=headers, json=payload)
    assert created.status_code == 201
    body = created.json()
    assert body["assigned_agent_key"] == "finance"
    assert body["capability"] == "profit.explain"
    assert body["external_write"] is False
    assert "user@example.com" not in body["instruction"]

    duplicate = client.post("/api/v1/agents/work-orders", headers=headers, json=payload)
    assert duplicate.status_code == 201
    assert duplicate.json()["id"] == body["id"]

    listed = client.get(f"/api/v1/agents/work-orders?store_id={store_id}", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["execution_enabled"] is False
    assert listed.json()["items"][0]["id"] == body["id"]
