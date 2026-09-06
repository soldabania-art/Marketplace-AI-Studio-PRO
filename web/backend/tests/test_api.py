import uuid

from fastapi.testclient import TestClient

from app.main import app

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


def test_register_login_and_me_contract():
    email = f"qa-{uuid.uuid4().hex}@example.com"
    password = "StrongPass123!"
    register = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": "QA Seller",
            "workspace_name": "QA Store",
        },
    )
    assert register.status_code == 201
    token = register.json()["access_token"]

    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    account = me.json()
    assert account["email"] == email
    assert account["workspace_name"] == "QA Store"
    assert account["role"] == "owner"
    assert account["plan_code"] == "trial"
    assert account["subscription_status"] == "trial"

    login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    assert login.json()["access_token"]
