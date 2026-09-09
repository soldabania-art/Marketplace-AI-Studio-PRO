import base64
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


def test_trial_subscription_exposes_server_entitlements_and_blocks_second_store():
    _, _, token = _register_user()
    headers = {"Authorization": f"Bearer {token}"}
    stores = client.get("/api/v1/stores", headers=headers).json()
    workspace_id = stores["workspaces"][0]["id"]
    billing = client.get("/api/v1/billing/subscription", headers=headers)
    assert billing.status_code == 200
    assert billing.json()["entitlements"]["stores_limit"] == 1
    assert billing.json()["entitlements"]["marketplace_publication"] is False
    second = client.post("/api/v1/stores", headers=headers, json={"workspace_id": workspace_id, "name": "Второй магазин"})
    assert second.status_code == 402


def test_checkout_never_activates_access_without_server_provider_confirmation():
    _, _, token = _register_user()
    response = client.post(
        "/api/v1/billing/checkout",
        headers={"Authorization": f"Bearer {token}"},
        json={"plan_code": "pro", "accepted_terms": True},
    )
    assert response.status_code == 503
    billing = client.get("/api/v1/billing/subscription", headers={"Authorization": f"Bearer {token}"}).json()
    assert billing["plan"] == "trial"
    assert billing["subscription_status"] == "trial"


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


def test_beginner_trial_starts_on_success_and_stops_after_five_cards(monkeypatch):
    _, _, token = _register_user()
    headers = {"Authorization": f"Bearer {token}"}
    store_id = client.get("/api/v1/stores", headers=headers).json()["stores"][0]["id"]
    before = client.get(f"/api/v1/beginner/trial?store_id={store_id}", headers=headers).json()
    assert before["status"] == "not_started"
    assert before["cards_remaining"] == 5
    monkeypatch.setattr("app.beginner_router.analyze_product_photo", lambda image: {
        "product_name_guess": "Товар",
        "category_guess": "Категория",
        "confidence": "medium",
        "visible_facts": [],
        "required_questions": ["Укажите материал"],
        "photo_warnings": [],
    })
    image = "data:image/jpeg;base64," + base64.b64encode(b"x" * 80).decode()
    last_analysis = None
    for remaining in range(4, -1, -1):
        response = client.post(
            "/api/v1/beginner/analyze-photo",
            headers=headers,
            json={"store_id": store_id, "image_data_url": image},
        )
        assert response.status_code == 200
        assert response.json()["trial"]["cards_remaining"] == remaining
        last_analysis = response.json()
    exhausted = client.get(f"/api/v1/beginner/trial?store_id={store_id}", headers=headers).json()
    assert exhausted["status"] == "exhausted"
    assert exhausted["read_only"] is True
    assert client.post(
        "/api/v1/beginner/analyze-photo",
        headers=headers,
        json={"store_id": store_id, "image_data_url": image},
    ).status_code == 402
    monkeypatch.setattr("app.beginner_router.generate_grounded_copy", lambda fact_set: {
        "wb_title": "Товар",
        "ozon_title": "Товар",
        "description": "Описание подтверждённого товара",
        "seo_phrases": ["товар"],
        "visual_plan": ["Главное фото"],
        "used_fact_ids": ["seller.confirmed.0"],
    })
    completed_fifth = client.post(
        "/api/v1/beginner/generate-draft",
        headers=headers,
        json={
            "store_id": store_id,
            "analysis": last_analysis["analysis"],
            "analysis_signature": last_analysis["analysis_signature"],
            "confirmed_facts": [{"label": "Название", "value": "Товар"}, {"label": "Категория", "value": "Категория"}],
        },
    )
    assert completed_fifth.status_code == 200


def test_failed_photo_analysis_does_not_start_or_consume_trial(monkeypatch):
    _, _, token = _register_user()
    headers = {"Authorization": f"Bearer {token}"}
    store_id = client.get("/api/v1/stores", headers=headers).json()["stores"][0]["id"]
    monkeypatch.setattr("app.beginner_router.analyze_product_photo", lambda image: (_ for _ in ()).throw(RuntimeError("AI unavailable")))
    image = "data:image/jpeg;base64," + base64.b64encode(b"x" * 80).decode()
    response = client.post("/api/v1/beginner/analyze-photo", headers=headers, json={"store_id": store_id, "image_data_url": image})
    assert response.status_code == 503
    status = client.get(f"/api/v1/beginner/trial?store_id={store_id}", headers=headers).json()
    assert status["status"] == "not_started"
    assert status["cards_used"] == 0
