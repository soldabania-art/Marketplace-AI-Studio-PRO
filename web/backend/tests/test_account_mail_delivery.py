"""T09B regression coverage for durable, private account mail delivery."""
import asyncio
import hashlib
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.account_mail import (
    EmailProviderRetryError,
    _build_message,
    deliver_account_email,
    queue_account_email,
)
from app.config import get_settings
from app.db import Base, SessionLocal, engine
from app.job_queue import HANDLERS, JobOwnershipLost, run_one
from app.main import app
from app.models import (
    AccountActionToken,
    AccountTokenPurpose,
    BackgroundJob,
    EmailDelivery,
    EmailDeliveryStatus,
    User,
)
from app.security import hash_password


Base.metadata.create_all(bind=engine)


def _settings(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "email_provider", "resend")
    monkeypatch.setattr(settings, "resend_api_key", "test-api-key")
    monkeypatch.setattr(settings, "email_from", "TROVENDI <mail@example.com>")
    monkeypatch.setattr(settings, "email_secret_key", Fernet.generate_key().decode())
    monkeypatch.setattr(settings, "frontend_url", "https://app.example.com")
    monkeypatch.setattr(settings, "email_max_attempts", 4)
    monkeypatch.setattr(settings, "email_unknown_retry_limit", 2)
    return settings


def _stage_delivery(monkeypatch, *, purpose=AccountTokenPurpose.verify_email):
    _settings(monkeypatch)
    with SessionLocal() as db:
        user = User(
            email=f"mail-{uuid.uuid4().hex}@example.com",
            password_hash=hash_password("StrongPass123!"),
        )
        db.add(user)
        db.flush()
        raw_token = "private-token-<unsafe>&" + uuid.uuid4().hex
        token = AccountActionToken(
            user_id=user.id,
            purpose=purpose,
            token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
        )
        db.add(token)
        db.flush()
        delivery = queue_account_email(db, user=user, token=token, raw_token=raw_token)
        db.commit()
        return delivery.id, user.id, token.id, raw_token


def test_token_delivery_and_job_are_staged_atomically_without_plaintext(monkeypatch):
    settings = _settings(monkeypatch)
    raw_token = "rollback-secret-<tag>"
    with SessionLocal() as db:
        user = User(email=f"rollback-{uuid.uuid4().hex}@example.com", password_hash=hash_password("StrongPass123!"))
        db.add(user)
        db.flush()
        token = AccountActionToken(
            user_id=user.id,
            purpose=AccountTokenPurpose.reset_password,
            token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
        )
        db.add(token)
        db.flush()
        delivery = queue_account_email(db, user=user, token=token, raw_token=raw_token)
        delivery_id = delivery.id
        assert delivery.status == EmailDeliveryStatus.queued
        db.rollback()

    with SessionLocal() as db:
        assert db.get(EmailDelivery, delivery_id) is None
        assert db.scalar(select(BackgroundJob).where(BackgroundJob.payload["delivery_id"].as_string() == delivery_id)) is None

    # Ciphertext and queue payload must never disclose the action token.
    delivery_id, _, _, raw_token = _stage_delivery(monkeypatch)
    with SessionLocal() as db:
        delivery = db.get(EmailDelivery, delivery_id)
        job = db.scalar(select(BackgroundJob).where(BackgroundJob.idempotency_key == f"account-mail:{delivery_id}"))
        assert job.payload == {"delivery_id": delivery_id}
        assert raw_token not in delivery.secret_ciphertext
        assert raw_token not in repr(job.payload)
        assert delivery.secret_ciphertext
        assert settings.resend_api_key not in repr(delivery.__dict__)


def test_message_uses_trusted_origin_and_escapes_html(monkeypatch):
    _settings(monkeypatch)
    message = _build_message(
        AccountTokenPurpose.verify_email,
        "victim@example.com",
        "token-<script>alert(1)</script>&x",
    )
    assert message["to"] == ["victim@example.com"]
    assert message["html"].count("https://app.example.com/verify-email?") == 1
    assert "<script>" not in message["html"]
    assert "%3Cscript%3E" in message["html"]
    assert "https://app.example.com/verify-email?" in message["text"]


def test_provider_acceptance_uses_stable_key_and_clears_secret(monkeypatch):
    delivery_id, _, _, _ = _stage_delivery(monkeypatch)
    calls = []

    class Response:
        status_code = 200
        headers = {}
        def json(self): return {"id": "resend-email-1"}

    async def send(message, idempotency_key):
        calls.append((message, idempotency_key))
        return Response()

    monkeypatch.setattr("app.account_mail._send_resend", send)
    asyncio.run(deliver_account_email({"delivery_id": delivery_id}, enforce_job_fence=False))

    with SessionLocal() as db:
        delivery = db.get(EmailDelivery, delivery_id)
        assert delivery.status == EmailDeliveryStatus.provider_accepted
        assert delivery.provider_message_id == "resend-email-1"
        assert delivery.secret_ciphertext == ""
        assert calls[0][1] == delivery.provider_idempotency_key


@pytest.mark.parametrize("kind", ["429", "500", "timeout"])
def test_retryable_provider_outcomes_stay_bounded_and_sanitized(monkeypatch, kind):
    delivery_id, _, _, _ = _stage_delivery(monkeypatch)

    async def send(_message, _key):
        if kind == "timeout":
            raise httpx.ReadTimeout("Authorization: Bearer leaked-secret")
        status = 429 if kind == "429" else 503
        return httpx.Response(status, headers={"Retry-After": "17"}, json={"message": "token=leaked-secret"})

    monkeypatch.setattr("app.account_mail._send_resend", send)
    with pytest.raises(EmailProviderRetryError) as error:
        asyncio.run(deliver_account_email({"delivery_id": delivery_id}, enforce_job_fence=False))
    assert error.value.retry_after_seconds >= (17 if kind == "429" else 1)
    with SessionLocal() as db:
        delivery = db.get(EmailDelivery, delivery_id)
        assert delivery.status == EmailDeliveryStatus.queued
        assert "leaked-secret" not in delivery.last_error


def test_dispatch_rejects_stale_recipient_consumed_or_expired_token(monkeypatch):
    for stale in ("recipient", "consumed", "expired", "inactive"):
        delivery_id, user_id, token_id, _ = _stage_delivery(monkeypatch)
        with SessionLocal() as db:
            user = db.get(User, user_id)
            token = db.get(AccountActionToken, token_id)
            if stale == "recipient": user.email = f"changed-{uuid.uuid4().hex}@example.com"
            if stale == "consumed": token.used_at = datetime.now(timezone.utc)
            if stale == "expired": token.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            if stale == "inactive": user.is_active = False
            db.commit()

        called = False
        async def send(*_args):
            nonlocal called
            called = True
        monkeypatch.setattr("app.account_mail._send_resend", send)
        asyncio.run(deliver_account_email({"delivery_id": delivery_id}, enforce_job_fence=False))
        assert not called
        with SessionLocal() as db:
            row = db.get(EmailDelivery, delivery_id)
            assert row.status == EmailDeliveryStatus.failed
            assert row.secret_ciphertext == ""


def test_handler_is_registered_for_the_existing_queue():
    assert HANDLERS["account.email.deliver"] is deliver_account_email


def test_real_existing_queue_claims_and_accepts_delivery(monkeypatch):
    delivery_id, _, _, _ = _stage_delivery(monkeypatch)
    with SessionLocal() as db:
        for job in db.scalars(select(BackgroundJob)).all():
            if job.idempotency_key != f"account-mail:{delivery_id}":
                job.status = "canceled"
        db.commit()

    class Response:
        status_code = 200
        headers = {}
        def json(self): return {"id": "queue-provider-id"}

    async def send(_message, _key): return Response()
    monkeypatch.setattr("app.account_mail._send_resend", send)
    assert asyncio.run(run_one("t09b-worker", lease_seconds=30, heartbeat_seconds=1)) is True
    with SessionLocal() as db:
        delivery = db.get(EmailDelivery, delivery_id)
        job = db.scalar(select(BackgroundJob).where(BackgroundJob.idempotency_key == f"account-mail:{delivery_id}"))
        assert delivery.status == EmailDeliveryStatus.provider_accepted
        assert job.status.value == "succeeded"


def test_stale_queue_attempt_is_fenced_before_provider_call(monkeypatch):
    delivery_id, _, _, _ = _stage_delivery(monkeypatch)
    with SessionLocal() as db:
        for job in db.scalars(select(BackgroundJob)).all():
            if job.idempotency_key != f"account-mail:{delivery_id}":
                job.status = "canceled"
        db.commit()
    called = False

    async def send(*_args):
        nonlocal called
        called = True

    def stale(_db):
        raise JobOwnershipLost("injected stale attempt")

    monkeypatch.setattr("app.account_mail._send_resend", send)
    monkeypatch.setattr("app.account_mail.assert_current_job_attempt_owned", stale)
    assert asyncio.run(run_one("stale-worker", lease_seconds=30, heartbeat_seconds=1)) is True
    assert not called
    with SessionLocal() as db:
        delivery = db.get(EmailDelivery, delivery_id)
        job = db.scalar(select(BackgroundJob).where(BackgroundJob.idempotency_key == f"account-mail:{delivery_id}"))
        assert delivery.status == EmailDeliveryStatus.queued
        assert delivery.submitting_attempt_id
        assert job.status.value == "retry"


def test_request_enqueue_failure_rolls_back_new_token_and_preserves_previous(monkeypatch):
    _settings(monkeypatch)
    test_client = TestClient(app)
    email = f"atomic-{uuid.uuid4().hex}@example.com"
    registered = test_client.post("/api/v1/auth/register", json={
        "email": email,
        "password": "StrongPass123!",
        "workspace_name": "Atomic Mail",
    })
    headers = {"Authorization": f"Bearer {registered.json()['access_token']}"}
    first = test_client.post("/api/v1/auth/email-verification/request", headers=headers)
    assert first.status_code == 200
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email))
        prior = db.scalar(select(AccountActionToken).where(
            AccountActionToken.user_id == user.id,
            AccountActionToken.used_at.is_(None),
        ))
        prior_id = prior.id

    def fail_enqueue(*_args, **_kwargs):
        raise RuntimeError("injected enqueue failure")

    monkeypatch.setattr("app.account_router.queue_account_email", fail_enqueue)
    with pytest.raises(RuntimeError, match="injected enqueue failure"):
        test_client.post("/api/v1/auth/email-verification/request", headers=headers)
    with SessionLocal() as db:
        active = db.scalars(select(AccountActionToken).where(
            AccountActionToken.user_id == user.id,
            AccountActionToken.used_at.is_(None),
        )).all()
        assert [row.id for row in active] == [prior_id]


def test_delivery_status_is_owner_scoped_and_returns_only_safe_fields(monkeypatch):
    _settings(monkeypatch)
    test_client = TestClient(app)

    def register(label):
        response = test_client.post("/api/v1/auth/register", json={
            "email": f"{label}-{uuid.uuid4().hex}@example.com",
            "password": "StrongPass123!",
            "workspace_name": label,
        })
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    owner = register("mail-owner")
    outsider = register("mail-outsider")
    queued = test_client.post("/api/v1/auth/email-verification/request", headers=owner).json()
    own = test_client.get(f"/api/v1/auth/email-deliveries/{queued['delivery_id']}", headers=owner)
    hidden = test_client.get(f"/api/v1/auth/email-deliveries/{queued['delivery_id']}", headers=outsider)
    assert own.status_code == 200
    assert set(own.json()) == {"id", "purpose", "status", "attempts", "provider_accepted_at", "failed_at"}
    assert hidden.status_code == 404
