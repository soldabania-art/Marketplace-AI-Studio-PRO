import uuid

from fastapi.testclient import TestClient

from app.db import Base, engine
from app.main import app

Base.metadata.create_all(bind=engine)
client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_dashboard_is_explicitly_demo_until_connected():
    payload = client.get("/api/v1/dashboard").json()
    assert payload["meta"]["mode"] == "demo"
    assert payload["meta"]["live_data"] is False


def test_integrations_start_disconnected():
    payload = client.get("/api/v1/integrations/status").json()
    assert payload["wildberries"]["connected"] is False
    assert payload["ozon"]["connected"] is False


def test_profit_formula_provenance():
    payload = client.get("/api/v1/profit").json()
    assert payload["formula"] == "payout - cogs - sku_ad_spend"


def test_billing_plans_are_public_and_provider_is_not_fake():
    payload = client.get("/api/v1/billing/plans").json()
    assert payload["provider"] == "not_configured"
    assert [plan["code"] for plan in payload["plans"]] == ["trial", "pro", "business"]


def _register_user():
    email = f"qa-{uuid.uuid4().hex}@example.com"
    password = "StrongPass123!"
    register = client.post("/api/v1/auth/register", json={"email":email,"password":password,"full_name":"QA Seller","workspace_name":"QA Store"})
    assert register.status_code == 201
    return email, password, register.json()["access_token"]


def test_register_login_and_me_contract():
    email, password, token = _register_user()
    me = client.get("/api/v1/auth/me", headers={"Authorization":f"Bearer {token}"})
    assert me.status_code == 200
    account = me.json()
    assert account["email"] == email
    assert account["workspace_name"] == "QA Store"
    assert account["role"] == "owner"
    assert account["plan_code"] == "trial"
    assert account["subscription_status"] == "trial"
    login = client.post("/api/v1/auth/login", json={"email":email,"password":password})
    assert login.status_code == 200
    assert login.json()["access_token"]


def test_session_can_be_listed_and_revoked():
    _, _, token = _register_user()
    headers = {"Authorization":f"Bearer {token}"}
    sessions = client.get("/api/v1/auth/sessions", headers=headers)
    assert sessions.status_code == 200
    current = next(row for row in sessions.json()["sessions"] if row["current"])
    revoked = client.delete(f"/api/v1/auth/sessions/{current['id']}", headers=headers)
    assert revoked.status_code == 200
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401


def test_email_verification_uses_one_time_hashed_token():
    _, _, access_token = _register_user()
    request = client.post("/api/v1/auth/email-verification/request", headers={"Authorization":f"Bearer {access_token}"})
    assert request.status_code == 200
    raw_token = request.json().get("development_token")
    assert raw_token
    confirm = client.post("/api/v1/auth/email-verification/confirm", json={"token":raw_token})
    assert confirm.status_code == 200
    assert confirm.json()["email_verified"] is True
    assert client.post("/api/v1/auth/email-verification/confirm", json={"token":raw_token}).status_code == 400


def test_password_reset_is_generic_and_one_time():
    email, old_password, old_token = _register_user()
    missing = client.post("/api/v1/auth/password-reset/request", json={"email":f"missing-{uuid.uuid4().hex}@example.com"})
    assert missing.status_code == 200
    assert "development_token" not in missing.json()
    reset_request = client.post("/api/v1/auth/password-reset/request", json={"email":email})
    assert reset_request.status_code == 200
    raw_token = reset_request.json().get("development_token")
    assert raw_token
    new_password = "NewStrongPass456!"
    assert client.post("/api/v1/auth/password-reset/confirm", json={"token":raw_token,"new_password":new_password}).status_code == 200
    assert client.get("/api/v1/auth/me", headers={"Authorization":f"Bearer {old_token}"}).status_code == 401
    assert client.post("/api/v1/auth/login", json={"email":email,"password":old_password}).status_code == 401
    assert client.post("/api/v1/auth/login", json={"email":email,"password":new_password}).status_code == 200
    assert client.post("/api/v1/auth/password-reset/confirm", json={"token":raw_token,"new_password":"AnotherStrong789!"}).status_code == 400


def test_beginner_project_persists_and_is_tenant_scoped():
    _, _, first_token = _register_user()
    first_headers = {"Authorization": f"Bearer {first_token}"}
    first_store = client.get("/api/v1/stores", headers=first_headers).json()["stores"][0]["id"]
    created = client.post(
        "/api/v1/beginner/projects",
        headers=first_headers,
        json={"store_id": first_store, "title": "Органайзер", "stage": "facts", "state": {"answers": {"0": "Металл"}}},
    )
    assert created.status_code == 201
    project_id = created.json()["id"]
    updated = client.patch(
        f"/api/v1/beginner/projects/{project_id}",
        headers=first_headers,
        json={"stage": "economics", "state": {"economics": {"profit_per_unit": 480}}},
    )
    assert updated.status_code == 200
    assert updated.json()["stage"] == "economics"
    listed = client.get(f"/api/v1/beginner/projects?store_id={first_store}", headers=first_headers)
    assert listed.status_code == 200
    assert listed.json()["projects"][0]["state"]["economics"]["profit_per_unit"] == 480

    _, _, second_token = _register_user()
    forbidden = client.patch(
        f"/api/v1/beginner/projects/{project_id}",
        headers={"Authorization": f"Bearer {second_token}"},
        json={"title": "Чужой проект"},
    )
    assert forbidden.status_code == 404
