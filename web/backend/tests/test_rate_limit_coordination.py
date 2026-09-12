"""T08C regression coverage for the shared fail-closed provider limiter."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet

from app import rate_limit
from app.config import Settings


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


def test_provider_retry_after_blocks_replay_in_shared_namespace(monkeypatch):
    monkeypatch.setattr(rate_limit, "get_settings", limiter_settings)
    monkeypatch.setattr(rate_limit, "_REDIS", BusyRedis())

    with pytest.raises(rate_limit.MarketplaceQuotaExceeded):
        asyncio.run(rate_limit.record_marketplace_backoff(
            "wildberries", "same-account", "cards", retry_after_seconds=3,
        ))


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
