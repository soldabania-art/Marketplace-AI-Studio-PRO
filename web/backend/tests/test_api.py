import base64
import uuid

from fastapi.testclient import TestClient

from app.db import Base, SessionLocal, engine
from app.main import app
from app.config import get_settings
from app.mfa_service import totp_code
from app.models import BackgroundJob, BusinessOperatingProfile, JobStatus, MarketplaceConnection, MarketplaceSnapshot, Membership, MembershipRole, OperationalAuditEvent, ProductCostProfile, Store

Base.metadata.create_all(bind=engine)
client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["x-request-id"]


def test_api_responses_are_not_cached_and_oversized_requests_are_rejected():
    response = client.get("/api/v1/billing/plans")
    assert response.headers["cache-control"] == "no-store, max-age=0"
    oversized = client.post(
        "/api/v1/auth/login",
        content=b"{}",
        headers={"content-type": "application/json", "content-length": str(20 * 1024 * 1024 + 1)},
    )
    assert oversized.status_code == 413


def test_weak_password_is_rejected_and_non_admin_cannot_list_users():
    weak = client.post("/api/v1/auth/register", json={
        "email": f"weak-{uuid.uuid4().hex}@example.com",
        "password": "password1234",
        "workspace_name": "Weak Password Test",
    })
    assert weak.status_code == 422
    _, _, token = _register_user()
    forbidden = client.get("/api/v1/admin/users", headers={"Authorization": f"Bearer {token}"})
    assert forbidden.status_code == 403


def test_failed_logins_are_bounded_by_source_ip(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "login_ip_max_failures", 2)
    source_ip = "2001:db8:" + ":".join(uuid.uuid4().hex[index:index + 4] for index in range(0, 16, 4))
    headers = {"x-forwarded-for": source_ip}
    for _ in range(2):
        response = client.post("/api/v1/auth/login", headers=headers, json={
            "email": f"missing-{uuid.uuid4().hex}@example.com",
            "password": "NotThePassword123!",
        })
        assert response.status_code == 401
    blocked = client.post("/api/v1/auth/login", headers=headers, json={
        "email": f"missing-{uuid.uuid4().hex}@example.com",
        "password": "NotThePassword123!",
    })
    assert blocked.status_code == 429


def test_dashboard_is_explicitly_demo_until_connected():
    payload = client.get("/api/v1/dashboard").json()
    assert payload["meta"]["mode"] == "demo"
    assert payload["meta"]["live_data"] is False


def test_integrations_start_disconnected():
    payload = client.get("/api/v1/integrations/status").json()
    assert payload["wildberries"]["connected"] is False
    assert payload["ozon"]["connected"] is False


def test_data_health_is_store_scoped_and_reports_source_freshness():
    _, _, token = _register_user()
    headers = {"Authorization": f"Bearer {token}"}
    user_id = client.get("/api/v1/auth/me", headers=headers).json()["id"]
    store_id = client.get("/api/v1/stores", headers=headers).json()["stores"][0]["id"]
    disconnected = client.get(f"/api/v1/data-health?store_id={store_id}", headers=headers)
    assert disconnected.status_code == 200
    assert disconnected.json()["overall_status"] == "disconnected"

    with SessionLocal() as db:
        assert db.get(Store, store_id) is not None
        db.add(MarketplaceConnection(user_id=user_id, store_id=store_id, marketplace="wildberries", encrypted_token="test", enabled=True))
        db.add_all([
            MarketplaceSnapshot(store_id=store_id, marketplace="wildberries", snapshot_type="catalog", payload={"count": 2}),
            MarketplaceSnapshot(store_id=store_id, marketplace="wildberries", snapshot_type="stocks", payload={"count": 2}),
            MarketplaceSnapshot(store_id=store_id, marketplace="wildberries", snapshot_type="sales_velocity_7d", payload={"count": 2}),
        ])
        db.commit()
    health = client.get(f"/api/v1/data-health?store_id={store_id}", headers=headers)
    assert health.status_code == 200
    result = health.json()
    assert result["safe_for_ai_decisions"] is True
    assert {item["key"]: item["status"] for item in result["sources"]}["stocks"] == "healthy"
    assert result["overall_status"] == "missing"

    with SessionLocal() as db:
        store = db.get(Store, store_id)
        db.add(BackgroundJob(
            workspace_id=store.workspace_id,
            store_id=store_id,
            job_type="marketplace.wb.analytics.sync",
            idempotency_key=f"health-error:{uuid.uuid4().hex}",
            status=JobStatus.dead,
            last_error="SECRET_API_TOKEN must never reach the browser",
        ))
        db.commit()
    failed = client.get(f"/api/v1/data-health?store_id={store_id}", headers=headers).json()
    assert failed["overall_status"] == "error"
    assert failed["safe_for_ai_decisions"] is False
    assert "SECRET_API_TOKEN" not in str(failed)

    _, _, other_token = _register_user()
    forbidden = client.get(f"/api/v1/data-health?store_id={store_id}", headers={"Authorization": f"Bearer {other_token}"})
    assert forbidden.status_code == 404


def test_onboarding_is_store_scoped_and_business_profile_requires_admin_confirmation():
    _, _, owner_token = _register_user()
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    store_id = client.get("/api/v1/stores", headers=owner_headers).json()["stores"][0]["id"]
    assessment = client.get(f"/api/v1/onboarding?store_id={store_id}", headers=owner_headers)
    assert assessment.status_code == 200
    assert assessment.json()["completion_percent"] == 25
    assert assessment.json()["profile_decision"]["state"] == "confirmation_required"
    assert assessment.json()["evidence"]["catalog_cards"] == 0
    assert len(assessment.json()["actions"]) <= 3

    _, _, analyst_token = _register_user()
    analyst_headers = {"Authorization": f"Bearer {analyst_token}"}
    analyst_id = client.get("/api/v1/auth/me", headers=analyst_headers).json()["id"]
    with SessionLocal() as db:
        store = db.get(Store, store_id)
        db.query(Membership).filter(Membership.user_id == analyst_id).delete()
        db.add(Membership(user_id=analyst_id, workspace_id=store.workspace_id, role=MembershipRole.analyst))
        db.commit()
    body = {"store_id": store_id, "operating_model": "manufacturer", "buys_finished_goods": False, "makes_products": True, "controls_rrp": False}
    forbidden = client.put("/api/v1/onboarding/profile", headers=analyst_headers, json=body)
    assert forbidden.status_code == 403
    import_forbidden = client.post(f"/api/v1/onboarding/import?store_id={store_id}", headers=analyst_headers)
    assert import_forbidden.status_code == 403

    confirmed = client.put("/api/v1/onboarding/profile", headers=owner_headers, json=body)
    assert confirmed.status_code == 200
    assert confirmed.json()["profile"]["operating_model"] == "manufacturer"
    assert confirmed.json()["completion_percent"] == 50
    with SessionLocal() as db:
        assert db.query(BusinessOperatingProfile).filter(BusinessOperatingProfile.store_id == store_id).count() == 1
        assert db.query(OperationalAuditEvent).filter(
            OperationalAuditEvent.store_id == store_id,
            OperationalAuditEvent.event_type == "onboarding.business_profile.confirmed",
        ).count() == 1

    repeated = client.put("/api/v1/onboarding/profile", headers=owner_headers, json=body)
    assert repeated.status_code == 200
    with SessionLocal() as db:
        assert db.query(OperationalAuditEvent).filter(
            OperationalAuditEvent.store_id == store_id,
            OperationalAuditEvent.event_type == "onboarding.business_profile.confirmed",
        ).count() == 1
    inconsistent = client.put("/api/v1/onboarding/profile", headers=owner_headers, json={**body, "makes_products": False})
    assert inconsistent.status_code == 422

    with SessionLocal() as db:
        store = db.get(Store, store_id)
        owner_id = client.get("/api/v1/auth/me", headers=owner_headers).json()["id"]
        db.add(MarketplaceConnection(user_id=owner_id, store_id=store_id, marketplace="wildberries", encrypted_token="test", enabled=True))
        db.commit()
    cost_body = {
        "store_id": store_id,
        "operating_model": "manufacturer",
        "components_rub": {"materials": "450.25", "direct_labor": "149.75"},
        "source_references": {"materials": "Техкарта №1", "direct_labor": "Наряд №2"},
        "confirmed": True,
    }
    cost_forbidden = client.patch("/api/v1/profit-center/costs/123456", headers=analyst_headers, json=cost_body)
    assert cost_forbidden.status_code == 403
    cost_saved = client.patch("/api/v1/profit-center/costs/123456", headers=owner_headers, json=cost_body)
    assert cost_saved.status_code == 200
    assert cost_saved.json()["cogs_rub"] == "600.00"
    assert cost_saved.json()["cost_profile"]["operating_model"] == "manufacturer"
    with SessionLocal() as db:
        cost = db.query(ProductCostProfile).filter(ProductCostProfile.store_id == store_id, ProductCostProfile.nm_id == 123456).one()
        assert cost.components == {"materials": 45025, "direct_labor": 14975}
        assert len(cost.calculation_sha256) == 64
        assert db.query(OperationalAuditEvent).filter(
            OperationalAuditEvent.store_id == store_id,
            OperationalAuditEvent.event_type == "profit.cost.confirmed",
        ).count() == 1
    started = client.post(f"/api/v1/onboarding/import?store_id={store_id}", headers=owner_headers)
    repeated_import = client.post(f"/api/v1/onboarding/import?store_id={store_id}", headers=owner_headers)
    assert started.status_code == 202
    assert repeated_import.status_code == 202
    assert started.json()["read_only"] is True
    assert {key: value["id"] for key, value in started.json()["jobs"].items()} == {key: value["id"] for key, value in repeated_import.json()["jobs"].items()}
    progress = client.get(f"/api/v1/onboarding?store_id={store_id}", headers=owner_headers).json()
    assert progress["import"]["resumable"] is True
    assert {item["state"] for item in progress["import"]["groups"]} == {"syncing"}
    assert len(progress["costing_questions"]) == 5
    with SessionLocal() as db:
        jobs = db.query(BackgroundJob).filter(BackgroundJob.store_id == store_id).all()
        assert len(jobs) == 3
        assert all((job.payload or {}).get("origin") == "onboarding" for job in jobs)

    _, _, outsider_token = _register_user()
    outsider = client.get(f"/api/v1/onboarding?store_id={store_id}", headers={"Authorization": f"Bearer {outsider_token}"})
    assert outsider.status_code == 404


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


def test_mfa_setup_login_recovery_and_single_use_challenge():
    email, password, token = _register_user()
    headers = {"Authorization": f"Bearer {token}"}
    setup = client.post("/api/v1/auth/mfa/setup", headers=headers, json={"password": password})
    assert setup.status_code == 200
    secret = setup.json()["secret"]
    confirm = client.post("/api/v1/auth/mfa/confirm", headers=headers, json={"code": totp_code(secret)})
    assert confirm.status_code == 200
    recovery_codes = confirm.json()["recovery_codes"]
    assert len(recovery_codes) == 10
    status_response = client.get("/api/v1/auth/mfa/status", headers=headers)
    assert status_response.json()["enabled"] is True
    assert status_response.json()["current_session_verified"] is True

    password_step = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert password_step.status_code == 200
    assert password_step.json()["mfa_required"] is True
    assert password_step.json()["access_token"] is None
    challenge = password_step.json()["mfa_challenge_token"]
    wrong = client.post("/api/v1/auth/mfa/login", json={"challenge_token": challenge, "code": "000000"})
    assert wrong.status_code == 401
    verified = client.post("/api/v1/auth/mfa/login", json={"challenge_token": challenge, "code": totp_code(secret)})
    assert verified.status_code == 200
    assert verified.json()["access_token"]
    assert client.post("/api/v1/auth/mfa/login", json={"challenge_token": challenge, "code": totp_code(secret)}).status_code == 400

    replay_step = client.post("/api/v1/auth/login", json={"email": email, "password": password}).json()
    replayed_totp = client.post("/api/v1/auth/mfa/login", json={"challenge_token": replay_step["mfa_challenge_token"], "code": totp_code(secret)})
    assert replayed_totp.status_code == 401

    recovery_step = client.post("/api/v1/auth/login", json={"email": email, "password": password}).json()
    recovered = client.post("/api/v1/auth/mfa/login", json={"challenge_token": recovery_step["mfa_challenge_token"], "code": recovery_codes[0]})
    assert recovered.status_code == 200
    next_step = client.post("/api/v1/auth/login", json={"email": email, "password": password}).json()
    reused = client.post("/api/v1/auth/mfa/login", json={"challenge_token": next_step["mfa_challenge_token"], "code": recovery_codes[0]})
    assert reused.status_code == 401


def test_sensitive_actions_require_short_lived_step_up():
    _, password, token = _register_user()
    headers = {"Authorization": f"Bearer {token}"}
    initial = client.get("/api/v1/auth/step-up/status", headers=headers)
    assert initial.status_code == 200
    assert initial.json()["verified"] is False
    blocked = client.post(
        "/api/v1/integrations/wildberries",
        headers=headers,
        json={"store_id": None, "token": "x" * 40},
    )
    assert blocked.status_code == 428
    assert client.post("/api/v1/auth/step-up", headers=headers, json={"password": "wrong"}).status_code == 401
    verified = client.post("/api/v1/auth/step-up", headers=headers, json={"password": password})
    assert verified.status_code == 200
    assert verified.json()["verified"] is True
    current = client.get("/api/v1/auth/step-up/status", headers=headers).json()
    assert current["verified"] is True
    sessions = client.get("/api/v1/auth/sessions", headers=headers).json()["sessions"]
    assert next(row for row in sessions if row["current"])["step_up_verified"] is True


def test_wrong_password_does_not_consume_mfa_code_during_step_up():
    _, password, token = _register_user()
    headers = {"Authorization": f"Bearer {token}"}
    setup = client.post("/api/v1/auth/mfa/setup", headers=headers, json={"password": password}).json()
    code = totp_code(setup["secret"])
    assert client.post("/api/v1/auth/mfa/confirm", headers=headers, json={"code": code}).status_code == 200
    assert client.post("/api/v1/auth/step-up", headers=headers, json={"password": "wrong", "code": code}).status_code == 401
    verified = client.post("/api/v1/auth/step-up", headers=headers, json={"password": password, "code": code})
    assert verified.status_code == 200


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
