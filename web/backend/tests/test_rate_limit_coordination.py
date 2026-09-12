"""T08C regression coverage for the shared fail-closed provider limiter."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet

from app import rate_limit
from app.config import Settings
from app.db import Base, SessionLocal, engine
from app.job_queue import _fail
from app.models import BackgroundJob, JobStatus

Base.metadata.create_all(bind=engine)


class BusyRedis:
    async def set(self, *args, **kwargs):
        return False

    async def pttl(self, *args, **kwargs):
        return 5_000


class FailedRedis:
    async def set(self, *args, **kwargs):
        raise ConnectionError("redis unavailable")


def limiter_settings(**overrides):
    values = {
        "marketplace_default_min_interval_seconds": 1.0,
        "marketplace_limiter_backend": "redis",
        "marketplace_limiter_max_wait_seconds": 0.01,
        "redis_key_prefix": "trovendi-test",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_busy_shared_quota_returns_bounded_429_instead_of_waiting_forever(monkeypatch):
    monkeypatch.setattr(rate_limit, "get_settings", limiter_settings)
    monkeypatch.setattr(rate_limit, "_REDIS", BusyRedis())

    with pytest.raises(rate_limit.MarketplaceQuotaExceeded) as raised:
        asyncio.run(asyncio.wait_for(
            rate_limit.wait_marketplace_slot("wildberries", "same-account", "cards"),
            timeout=0.2,
        ))
    assert raised.value.retry_after_seconds >= 1


def test_redis_failure_is_normalized_and_never_falls_back_to_memory(monkeypatch):
    monkeypatch.setattr(rate_limit, "get_settings", limiter_settings)
    monkeypatch.setattr(rate_limit, "_REDIS", FailedRedis())
    memory_called = False

    async def memory(*args, **kwargs):
        nonlocal memory_called
        memory_called = True

    monkeypatch.setattr(rate_limit, "_memory_wait", memory)
    with pytest.raises(rate_limit.MarketplaceLimiterUnavailable):
        asyncio.run(rate_limit.wait_marketplace_slot("wildberries", "same-account", "cards"))
    assert memory_called is False


def test_redis_failure_prevents_provider_call(monkeypatch):
    from app import wb_content

    monkeypatch.setattr(rate_limit, "get_settings", limiter_settings)
    monkeypatch.setattr(rate_limit, "_REDIS", FailedRedis())
    provider_called = False

    class ForbiddenClient:
        def __init__(self, *args, **kwargs):
            nonlocal provider_called
            provider_called = True

    monkeypatch.setattr(wb_content.httpx, "AsyncClient", ForbiddenClient)
    with pytest.raises(rate_limit.MarketplaceLimiterUnavailable):
        asyncio.run(wb_content.fetch_wb_card("same-account", nm_id=1, vendor_code="sku"))
    assert provider_called is False


def test_provider_retry_after_blocks_replay_in_shared_namespace(monkeypatch):
    monkeypatch.setattr(rate_limit, "get_settings", limiter_settings)
    monkeypatch.setattr(rate_limit, "_REDIS", BusyRedis())

    with pytest.raises(rate_limit.MarketplaceQuotaExceeded):
        asyncio.run(rate_limit.record_marketplace_backoff(
            "wildberries", "same-account", "cards", retry_after_seconds=3,
        ))


def test_retry_after_supports_seconds_and_http_date():
    seconds = SimpleNamespace(headers={"Retry-After": "12"})
    future = datetime.now(timezone.utc) + timedelta(seconds=30)
    http_date = SimpleNamespace(headers={"Retry-After": future.strftime("%a, %d %b %Y %H:%M:%S GMT")})
    assert rate_limit.retry_after_seconds(seconds) == 12
    assert 20 <= rate_limit.retry_after_seconds(http_date) <= 30


def test_worker_retry_is_scheduled_after_shared_cooldown():
    key = f"t08c-cooldown-{__import__('uuid').uuid4().hex}"
    with SessionLocal() as db:
        job = BackgroundJob(
            job_type="test.t08c",
            idempotency_key=key,
            status=JobStatus.running,
            attempts=1,
            max_attempts=5,
            locked_by="worker",
            attempt_id="attempt",
        )
        db.add(job)
        db.commit()
        job_id = job.id
    before = datetime.now(timezone.utc)
    with SessionLocal() as db:
        assert _fail(
            db, job_id, "worker", "attempt", rate_limit.MarketplaceQuotaExceeded(120)
        ) is True
    with SessionLocal() as db:
        stored = db.get(BackgroundJob, job_id)
        available = stored.available_at
        if available.tzinfo is None:
            available = available.replace(tzinfo=timezone.utc)
        assert stored.status == JobStatus.retry
        assert available >= before + timedelta(seconds=120)


def test_production_requires_shared_redis_limiter():
    key = Fernet.generate_key().decode()
    common = {
        "environment": "production",
        "database_url": "postgresql+psycopg://db/app?sslmode=require",
        "jwt_secret": "x" * 48,
        "marketplace_token_key": key,
        "mfa_encryption_key": key,
        "frontend_url": "https://example.test",
        "_env_file": None,
    }
    with pytest.raises(ValueError, match="Redis limiter"):
        Settings(**common, marketplace_limiter_backend="memory")
    with pytest.raises(ValueError, match="REDIS_URL"):
        Settings(**common, marketplace_limiter_backend="redis", redis_url="")
