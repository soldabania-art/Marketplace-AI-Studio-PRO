"""Shared quota checks against a real Redis service."""
from __future__ import annotations

import asyncio
import os
import uuid

import pytest

from app import rate_limit


REDIS_URL = os.getenv("MARKETPLACE_REDIS_URL", "")


@pytest.mark.skipif(not REDIS_URL, reason="real Redis service is not configured")
def test_two_redis_clients_share_provider_account_quota(monkeypatch):
    from redis.asyncio import Redis

    async def scenario():
        token = f"t08c-{uuid.uuid4().hex}"
        first = Redis.from_url(REDIS_URL, decode_responses=True)
        second = Redis.from_url(REDIS_URL, decode_responses=True)
        key = f"mai:rate:{rate_limit.limiter_key('wildberries', token, 'cards')}"
        try:
            rate_limit._REDIS = first
            await rate_limit.wait_marketplace_slot(
                "wildberries", token, "cards", min_interval_seconds=10,
            )
            rate_limit._REDIS = second
            with pytest.raises(rate_limit.MarketplaceQuotaExceeded) as raised:
                await rate_limit.wait_marketplace_slot(
                    "wildberries", token, "cards", min_interval_seconds=10,
                )
            assert raised.value.retry_after_seconds >= 1
        finally:
            await second.delete(key)
            await first.aclose()
            await second.aclose()
            rate_limit._REDIS = None

    asyncio.run(scenario())


@pytest.mark.skipif(not REDIS_URL, reason="real Redis service is not configured")
def test_retry_after_is_shared_and_blocks_replay(monkeypatch):
    from redis.asyncio import Redis

    async def scenario():
        token = f"t08c-{uuid.uuid4().hex}"
        first = Redis.from_url(REDIS_URL, decode_responses=True)
        second = Redis.from_url(REDIS_URL, decode_responses=True)
        key = f"mai:rate:{rate_limit.limiter_key('wildberries', token, 'cards')}"
        try:
            rate_limit._REDIS = first
            with pytest.raises(rate_limit.MarketplaceQuotaExceeded):
                await rate_limit.record_marketplace_backoff(
                    "wildberries", token, "cards", retry_after_seconds=30,
                )
            rate_limit._REDIS = second
            with pytest.raises(rate_limit.MarketplaceQuotaExceeded) as raised:
                await rate_limit.wait_marketplace_slot(
                    "wildberries", token, "cards", min_interval_seconds=0.01,
                )
            assert raised.value.retry_after_seconds >= 20
        finally:
            await second.delete(key)
            await first.aclose()
            await second.aclose()
            rate_limit._REDIS = None

    asyncio.run(scenario())
