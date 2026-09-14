"""Independent review regressions: never re-send outside the safe window."""
import asyncio
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from app import account_mail
from app.config import get_settings
from app.db import SessionLocal
from app.models import AccountActionToken, EmailDelivery, EmailDeliveryStatus
from test_account_mail_delivery import _stage_delivery


@pytest.mark.parametrize('expired', ['provider_window', 'token'])
def test_crashed_dispatch_expiry_is_unknown_and_never_sends(monkeypatch, expired):
    delivery_id, _, token_id, _ = _stage_delivery(monkeypatch)
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        delivery = db.get(EmailDelivery, delivery_id)
        token = db.get(AccountActionToken, token_id)
        delivery.submitting_attempt_id = 'crashed-worker'
        delivery.submitting_at = now - timedelta(hours=25)
        delivery.first_submitted_at = now - timedelta(hours=25 if expired == 'provider_window' else 1)
        token.expires_at = delivery.expires_at = now + timedelta(hours=10) if expired == 'provider_window' else now - timedelta(seconds=1)
        db.commit()
    calls = []
    async def send(*args):
        calls.append(args)
        return httpx.Response(200, json={'id': 'mock-provider-id'})
    monkeypatch.setattr(account_mail, '_send_resend', send)
    asyncio.run(account_mail.deliver_account_email({'delivery_id': delivery_id}, enforce_job_fence=False))
    assert not calls
    with SessionLocal() as db:
        delivery = db.get(EmailDelivery, delivery_id)
        assert delivery.status == EmailDeliveryStatus.outcome_unknown
        assert delivery.secret_ciphertext == ''


def test_cleanup_does_not_call_a_crashed_submission_definitely_failed(monkeypatch):
    delivery_id, _, _, _ = _stage_delivery(monkeypatch)
    with SessionLocal() as db:
        delivery = db.get(EmailDelivery, delivery_id)
        delivery.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        delivery.submitting_attempt_id = 'crashed-worker'
        db.commit()
    account_mail.cleanup_expired_email_secrets_once()
    with SessionLocal() as db:
        delivery = db.get(EmailDelivery, delivery_id)
        assert delivery.status == EmailDeliveryStatus.outcome_unknown
        assert delivery.secret_ciphertext == ''


def test_retry_reuses_saved_message_and_key_despite_configuration_change(monkeypatch):
    delivery_id, _, _, _ = _stage_delivery(monkeypatch)
    calls = []
    async def send(message, key):
        calls.append((message, key))
        if len(calls) == 1:
            raise httpx.ReadTimeout('do-not-store-sensitive-body')
        return httpx.Response(200, json={'id': 'mock-provider-id'})
    monkeypatch.setattr(account_mail, '_send_resend', send)
    with pytest.raises(account_mail.EmailProviderRetryError):
        asyncio.run(account_mail.deliver_account_email({'delivery_id': delivery_id}, enforce_job_fence=False))
    settings = get_settings()
    monkeypatch.setattr(settings, 'frontend_url', 'https://changed.example.com')
    monkeypatch.setattr(settings, 'email_from', 'changed@example.com')
    asyncio.run(account_mail.deliver_account_email({'delivery_id': delivery_id}, enforce_job_fence=False))
    assert calls[0] == calls[1]
    asyncio.run(account_mail.deliver_account_email({'delivery_id': delivery_id}, enforce_job_fence=False))
    assert len(calls) == 2


@pytest.mark.parametrize('provider_id', [None, '', 42])
def test_invalid_success_identifier_is_never_provider_accepted(monkeypatch, provider_id):
    delivery_id, _, _, _ = _stage_delivery(monkeypatch)
    async def send(*args):
        return httpx.Response(200, json={'id': provider_id})
    monkeypatch.setattr(account_mail, '_send_resend', send)
    with pytest.raises(account_mail.EmailProviderRetryError):
        asyncio.run(account_mail.deliver_account_email({'delivery_id': delivery_id}, enforce_job_fence=False))
    with SessionLocal() as db:
        delivery = db.get(EmailDelivery, delivery_id)
        assert delivery.status != EmailDeliveryStatus.provider_accepted
        assert delivery.may_have_been_accepted


def test_definite_rejection_after_an_ambiguous_send_remains_unknown(monkeypatch):
    delivery_id, _, _, _ = _stage_delivery(monkeypatch)
    replies = iter([503, 400])
    async def send(*args):
        return httpx.Response(next(replies), json={'message': 'secret-provider-body'})
    monkeypatch.setattr(account_mail, '_send_resend', send)
    with pytest.raises(account_mail.EmailProviderRetryError):
        asyncio.run(account_mail.deliver_account_email({'delivery_id': delivery_id}, enforce_job_fence=False))
    asyncio.run(account_mail.deliver_account_email({'delivery_id': delivery_id}, enforce_job_fence=False))
    with SessionLocal() as db:
        delivery = db.get(EmailDelivery, delivery_id)
        assert delivery.status == EmailDeliveryStatus.outcome_unknown
        assert delivery.secret_ciphertext == ''
        assert 'secret-provider-body' not in delivery.last_error


def test_duplicate_after_provider_window_cannot_downgrade_acceptance(monkeypatch):
    delivery_id, _, _, _ = _stage_delivery(monkeypatch)
    calls = []
    async def send(*args):
        calls.append(args)
        return httpx.Response(200, json={'id': 'accepted-id'})
    monkeypatch.setattr(account_mail, '_send_resend', send)
    asyncio.run(account_mail.deliver_account_email({'delivery_id': delivery_id}, enforce_job_fence=False))
    with SessionLocal() as db:
        delivery = db.get(EmailDelivery, delivery_id)
        delivery.first_submitted_at = datetime.now(timezone.utc) - timedelta(hours=25)
        db.commit()
    asyncio.run(account_mail.deliver_account_email({'delivery_id': delivery_id}, enforce_job_fence=False))
    assert len(calls) == 1
    with SessionLocal() as db:
        assert db.get(EmailDelivery, delivery_id).status == EmailDeliveryStatus.provider_accepted
