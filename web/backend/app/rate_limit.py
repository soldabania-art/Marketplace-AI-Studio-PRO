"""Marketplace API rate limiting with pluggable memory/Redis backends.

Keys contain only a SHA-256 token fingerprint, never the plaintext token.
Redis is required for multi-replica production; memory remains convenient locally.
"""
import asyncio
import hashlib
import time
from dataclasses import dataclass

from .config import get_settings

@dataclass
class _Bucket:
    lock: asyncio.Lock
    next_at: float = 0.0

_BUCKETS: dict[str, _Bucket] = {}
_REDIS = None


def token_fingerprint(token: str) -> str:
    return hashlib.sha256(token.encode('utf-8')).hexdigest()[:24]


def limiter_key(marketplace: str, token: str, endpoint_group: str) -> str:
    return f'{marketplace}:{token_fingerprint(token)}:{endpoint_group}'


async def _memory_wait(key: str, interval: float) -> None:
    bucket = _BUCKETS.setdefault(key, _Bucket(asyncio.Lock()))
    async with bucket.lock:
        now = time.monotonic()
        delay = max(0.0, bucket.next_at - now)
        if delay:
            await asyncio.sleep(delay)
        bucket.next_at = time.monotonic() + interval


async def _redis_client():
    global _REDIS
    if _REDIS is None:
        from redis.asyncio import Redis
        settings = get_settings()
        if not settings.redis_url:
            raise RuntimeError('MARKETPLACE_REDIS_URL is required for Redis rate limiting')
        _REDIS = Redis.from_url(settings.redis_url, decode_responses=True)
    return _REDIS


async def _redis_wait(key: str, interval: float) -> None:
    if interval <= 0:
        return
    settings = get_settings()
    redis = await _redis_client()
    redis_key = f'{settings.redis_key_prefix}:rate:{key}'
    ttl_ms = max(1, int(interval * 1000))
    # SET NX PX is atomic across API/worker replicas. We wait for the remaining
    # TTL and retry instead of maintaining process-local timing state.
    while True:
        acquired = await redis.set(redis_key, '1', nx=True, px=ttl_ms)
        if acquired:
            return
        remaining = await redis.pttl(redis_key)
        await asyncio.sleep(max(0.01, (remaining if remaining and remaining > 0 else ttl_ms) / 1000.0))


async def wait_marketplace_slot(marketplace: str, token: str, endpoint_group: str, *, min_interval_seconds: float | None = None) -> None:
    settings = get_settings()
    interval = settings.marketplace_default_min_interval_seconds if min_interval_seconds is None else min_interval_seconds
    interval = max(0.0, float(interval))
    key = limiter_key(marketplace, token, endpoint_group)
    backend = settings.marketplace_limiter_backend.strip().lower()
    if backend == 'redis':
        await _redis_wait(key, interval)
        return
    if backend != 'memory':
        raise RuntimeError(f'Unsupported marketplace limiter backend: {backend}')
    await _memory_wait(key, interval)
