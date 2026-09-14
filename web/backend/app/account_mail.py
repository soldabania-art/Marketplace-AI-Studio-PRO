"""Durable transactional email delivery for account actions.

Account mail is scoped to the account itself. It is not a marketplace write and
must not depend on an arbitrary store STOP state. The queue attempt fence,
immutable provider request, and Resend idempotency key protect the external
effect instead.
"""
import asyncio
import hashlib
import html
import json
import logging
import math
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlencode

import httpx
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select

from .config import get_settings
from .db import SessionLocal
from .job_queue import (
    assert_current_job_attempt_owned,
    current_job_attempt,
    enqueue,
    register_handler,
    safe_job_error,
)
from .models import (
    AccountActionToken,
    AccountTokenPurpose,
    EmailDelivery,
    EmailDeliveryStatus,
    User,
)

logger = logging.getLogger(__name__)


class EmailProviderRetryError(RuntimeError):
    def __init__(self, category: str, retry_after_seconds: float = 1):
        self.retry_after_seconds = max(1, int(math.ceil(retry_after_seconds)))
        super().__init__(f"Email provider retry required: {category}")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _cipher() -> Fernet:
    key = get_settings().email_secret_key
    if not key:
        raise RuntimeError("Email secret encryption is not configured")
    try:
        return Fernet(key.encode())
    except Exception as exc:
        raise RuntimeError("Email secret encryption is invalid") from exc


def _build_message(purpose: AccountTokenPurpose, recipient: str, raw_token: str) -> dict:
    settings = get_settings()
    route = "/verify-email" if purpose == AccountTokenPurpose.verify_email else "/reset-password"
    link = f"{settings.frontend_origin}{route}?{urlencode({'token': raw_token})}"
    if purpose == AccountTokenPurpose.verify_email:
        subject, heading, action = "Подтвердите email в TROVENDI", "Подтверждение email", "Подтвердить email"
    else:
        subject, heading, action = "Восстановление пароля TROVENDI", "Восстановление пароля", "Сменить пароль"
    safe_link = html.escape(link, quote=True)
    return {
        "from": settings.email_from,
        "to": [recipient],
        "subject": subject,
        "html": (
            f"<h1>{html.escape(heading)}</h1>"
            f"<p><a href=\"{safe_link}\">{html.escape(action)}</a></p>"
            "<p>Если вы не запрашивали это действие, проигнорируйте письмо.</p>"
        ),
        "text": (
            f"{heading}\n\n{action}: {link}\n\n"
            "Если вы не запрашивали это действие, проигнорируйте письмо."
        ),
    }


def queue_account_email(db, *, user: User, token: AccountActionToken, raw_token: str) -> EmailDelivery:
    """Stage delivery and an existing-queue outbox row in caller transaction."""
    settings = get_settings()
    if not settings.email_is_configured:
        raise RuntimeError("Email provider is not configured")
    message = _build_message(token.purpose, user.email, raw_token)
    serialized = json.dumps(message, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    delivery = EmailDelivery(
        user_id=user.id,
        token_id=token.id,
        purpose=token.purpose,
        recipient=user.email,
        provider="resend",
        provider_idempotency_key=f"account-action/{token.id}",
        provider_payload_sha256=hashlib.sha256(serialized.encode()).hexdigest(),
        secret_ciphertext=_cipher().encrypt(serialized.encode()).decode(),
        expires_at=token.expires_at,
    )
    db.add(delivery)
    db.flush()
    enqueue(
        db,
        job_type="account.email.deliver",
        idempotency_key=f"account-mail:{delivery.id}",
        payload={"delivery_id": delivery.id},
        max_attempts=max(1, settings.email_max_attempts),
        priority=20,
    )
    return delivery


def _decode_message(delivery: EmailDelivery) -> dict:
    try:
        serialized = _cipher().decrypt(delivery.secret_ciphertext.encode()).decode()
    except (InvalidToken, UnicodeDecodeError) as exc:
        raise RuntimeError("Email delivery secret cannot be decrypted") from exc
    if hashlib.sha256(serialized.encode()).hexdigest() != delivery.provider_payload_sha256:
        raise RuntimeError("Email provider payload integrity check failed")
    value = json.loads(serialized)
    if not isinstance(value, dict):
        raise RuntimeError("Email provider payload is invalid")
    return value


def _mark_terminal(delivery: EmailDelivery, category: str) -> None:
    delivery.status = (
        EmailDeliveryStatus.outcome_unknown
        if delivery.may_have_been_accepted
        else EmailDeliveryStatus.failed
    )
    delivery.failed_at = _utcnow()
    delivery.last_error = category[:500]
    delivery.secret_ciphertext = ""
    delivery.submitting_attempt_id = ""
    delivery.submitting_at = None


def _validate_dispatch(db, delivery: EmailDelivery) -> bool:
    if delivery.status in {
        EmailDeliveryStatus.provider_accepted,
        EmailDeliveryStatus.failed,
        EmailDeliveryStatus.outcome_unknown,
    }:
        return False
    now = _utcnow()
    user = db.get(User, delivery.user_id)
    token = db.get(AccountActionToken, delivery.token_id)
    reason = ""
    if user is None or not user.is_active:
        reason = "account_unavailable"
    elif user.email != delivery.recipient:
        reason = "recipient_changed"
    elif token is None or token.user_id != user.id or token.purpose != delivery.purpose:
        reason = "token_mismatch"
    elif token.used_at is not None:
        reason = "token_consumed"
    elif _aware(token.expires_at) <= now or _aware(delivery.expires_at) <= now:
        reason = "token_expired"
    elif delivery.purpose == AccountTokenPurpose.verify_email and user.email_verified:
        reason = "email_already_verified"
    if reason:
        _mark_terminal(delivery, reason)
        return False
    return True


async def _send_resend(message: dict, idempotency_key: str) -> httpx.Response:
    settings = get_settings()
    timeout = httpx.Timeout(max(0.1, float(settings.email_provider_timeout_seconds)))
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        return await client.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {settings.resend_api_key}",
                "Content-Type": "application/json",
                "Idempotency-Key": idempotency_key,
            },
            json=message,
        )


def _retry_after(response: httpx.Response) -> int:
    value = response.headers.get("Retry-After", "1")
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        try:
            retry_at = parsedate_to_datetime(value)
            if retry_at.tzinfo is None:
                retry_at = retry_at.replace(tzinfo=timezone.utc)
            return max(1, int(math.ceil((retry_at - _utcnow()).total_seconds())))
        except (TypeError, ValueError, OverflowError):
            return 1


def _persist_retry_or_terminal(
    delivery_id: str,
    *,
    category: str,
    ambiguous: bool,
    attempt_number: int,
    retry_after: int = 1,
) -> None:
    settings = get_settings()
    with SessionLocal() as db:
        delivery = db.scalar(select(EmailDelivery).where(EmailDelivery.id == delivery_id).with_for_update())
        if delivery is None or delivery.status != EmailDeliveryStatus.queued:
            db.rollback()
            return
        if ambiguous:
            delivery.unknown_outcomes += 1
            delivery.may_have_been_accepted = True
        delivery.last_error = safe_job_error(RuntimeError(category))
        delivery.submitting_attempt_id = ""
        delivery.submitting_at = None
        now = _utcnow()
        exhausted = attempt_number >= max(1, settings.email_max_attempts)
        ambiguity_exhausted = (
            delivery.may_have_been_accepted
            and delivery.unknown_outcomes >= max(1, settings.email_unknown_retry_limit)
        )
        token_window_ends = _aware(delivery.expires_at)
        provider_window_ends = (
            _aware(delivery.first_submitted_at) + timedelta(hours=23)
            if delivery.first_submitted_at
            else token_window_ends
        )
        retry_window_seconds = (min(token_window_ends, provider_window_ends) - now).total_seconds()
        if exhausted or ambiguity_exhausted or max(1, retry_after) >= retry_window_seconds:
            _mark_terminal(
                delivery,
                "provider_outcome_unknown_terminal"
                if delivery.may_have_been_accepted
                else "provider_retry_exhausted",
            )
        db.commit()
        terminal = delivery.status in {EmailDeliveryStatus.failed, EmailDeliveryStatus.outcome_unknown}
    if not terminal:
        raise EmailProviderRetryError(category, retry_after)


def _response_name(response: httpx.Response) -> str:
    try:
        body = response.json()
    except Exception:
        return ""
    return body.get("name", "") if isinstance(body, dict) else ""


@register_handler("account.email.deliver")
async def deliver_account_email(payload: dict, *, enforce_job_fence: bool = True) -> None:
    delivery_id = payload.get("delivery_id")
    if not isinstance(delivery_id, str) or not delivery_id:
        raise RuntimeError("Account email job requires delivery_id")
    settings = get_settings()
    if not settings.email_is_configured:
        raise RuntimeError("Email provider is not configured")
    attempt = current_job_attempt() if enforce_job_fence else None
    attempt_number = attempt.attempt_number if attempt else 1
    attempt_id = attempt.attempt_id if attempt else f"test-{attempt_number}"

    with SessionLocal() as db:
        delivery = db.scalar(select(EmailDelivery).where(EmailDelivery.id == delivery_id).with_for_update())
        if delivery is None:
            return
        if delivery.status in {
            EmailDeliveryStatus.provider_accepted,
            EmailDeliveryStatus.failed,
            EmailDeliveryStatus.outcome_unknown,
        }:
            return
        if delivery.submitting_attempt_id:
            # A prior committed submission without an outcome may have reached
            # the provider, even if the token became stale afterwards.
            delivery.may_have_been_accepted = True
            delivery.unknown_outcomes += 1
        now = _utcnow()
        provider_window_expired = bool(
            delivery.first_submitted_at
            and _aware(delivery.first_submitted_at) + timedelta(hours=23) <= now
        )
        retry_budget_exhausted = (
            delivery.submit_attempts >= max(1, settings.email_max_attempts)
            or delivery.unknown_outcomes >= max(1, settings.email_unknown_retry_limit)
        )
        if provider_window_expired or retry_budget_exhausted:
            _mark_terminal(delivery, "provider_outcome_unknown_terminal")
            db.commit()
            return
        if not _validate_dispatch(db, delivery):
            db.commit()
            return
        try:
            message = _decode_message(delivery)
        except Exception:
            _mark_terminal(delivery, "delivery_secret_unavailable")
            db.commit()
            return
        delivery.submit_attempts += 1
        delivery.submitting_attempt_id = attempt_id
        delivery.submitting_at = _utcnow()
        if delivery.first_submitted_at is None:
            delivery.first_submitted_at = delivery.submitting_at
        delivery.last_error = ""
        provider_key = delivery.provider_idempotency_key
        db.commit()

    if enforce_job_fence:
        with SessionLocal() as db:
            assert_current_job_attempt_owned(db)
            db.commit()
        if attempt.ownership_lost.is_set():
            raise RuntimeError("Email queue attempt lost ownership before provider call")

    try:
        response = await _send_resend(message, provider_key)
    except (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError):
        _persist_retry_or_terminal(
            delivery_id,
            category="provider_outcome_unknown",
            ambiguous=True,
            attempt_number=attempt_number,
        )
        return

    response_name = _response_name(response) if response.status_code == 409 else ""
    if response.status_code == 429 or (
        response.status_code == 409 and response_name == "concurrent_idempotent_requests"
    ):
        _persist_retry_or_terminal(
            delivery_id,
            category=f"provider_retryable_http_{response.status_code}",
            ambiguous=False,
            attempt_number=attempt_number,
            retry_after=_retry_after(response),
        )
        return
    if response.status_code >= 500:
        _persist_retry_or_terminal(
            delivery_id,
            category="provider_server_error",
            ambiguous=True,
            attempt_number=attempt_number,
        )
        return

    if 200 <= response.status_code < 300:
        try:
            provider_id = response.json()["id"]
            if not isinstance(provider_id, str) or not provider_id.strip():
                raise ValueError("missing provider id")
            provider_id = provider_id.strip()
        except Exception:
            _persist_retry_or_terminal(
                delivery_id,
                category="provider_outcome_unknown",
                ambiguous=True,
                attempt_number=attempt_number,
            )
            return
        with SessionLocal() as db:
            delivery = db.scalar(select(EmailDelivery).where(EmailDelivery.id == delivery_id).with_for_update())
            if delivery is None or delivery.status != EmailDeliveryStatus.queued:
                db.rollback()
                return
            if delivery.submitting_attempt_id != attempt_id:
                db.rollback()
                raise RuntimeError("Email delivery attempt was superseded")
            delivery.status = EmailDeliveryStatus.provider_accepted
            delivery.provider_message_id = provider_id[:160]
            delivery.provider_accepted_at = _utcnow()
            delivery.secret_ciphertext = ""
            delivery.submitting_attempt_id = ""
            delivery.submitting_at = None
            delivery.last_error = ""
            db.commit()
        return

    with SessionLocal() as db:
        delivery = db.scalar(select(EmailDelivery).where(EmailDelivery.id == delivery_id).with_for_update())
        if delivery is not None and delivery.status == EmailDeliveryStatus.queued:
            if response.status_code == 409:
                delivery.may_have_been_accepted = True
                delivery.unknown_outcomes += 1
            _mark_terminal(delivery, f"provider_rejected_http_{response.status_code}")
            db.commit()


def cleanup_expired_email_secrets_once() -> int:
    """Remove expired action material, including rows whose queue job died."""
    now = _utcnow()
    with SessionLocal() as db:
        rows = db.scalars(select(EmailDelivery).where(
            EmailDelivery.secret_ciphertext != "",
            EmailDelivery.expires_at <= now,
        ).with_for_update()).all()
        for delivery in rows:
            if delivery.submitting_attempt_id:
                delivery.may_have_been_accepted = True
                delivery.unknown_outcomes += 1
            if delivery.status == EmailDeliveryStatus.queued:
                _mark_terminal(delivery, "token_expired")
            else:
                delivery.secret_ciphertext = ""
                delivery.submitting_attempt_id = ""
                delivery.submitting_at = None
        db.commit()
        return len(rows)


async def account_mail_cleanup_forever(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            cleanup_expired_email_secrets_once()
        except Exception as exc:
            logger.error("Expired account mail secret cleanup failed error_type=%s", type(exc).__name__)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=300)
        except asyncio.TimeoutError:
            pass
