"""Marketplace API rate limiting with pluggable memory/Redis backends.

Keys contain only a SHA-256 token fingerprint, never the plaintext token.
Redis is required for multi-replica production; memory remains convenient locally.
"""
import asyncio
import hashlib
import math
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from .config import get_settings

@dataclass
class _Bucket:
    lock: asyncio.Lock
    next_at: float = 0.0

_BUCKETS: dict[str, _Bucket] = {}
_REDIS = None


class MarketplaceQuotaExceeded(RuntimeError):
    def __init__(self, retry_after_seconds: float):
        self.retry_after_seconds = max(1, int(math.ceil(retry_after_seconds)))
        super().__init__(f'Marketplace quota is busy; retry after {self.retry_after_seconds} seconds')


class MarketplaceLimiterUnavailable(RuntimeError):
    pass


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
        timeout = max(0.05, float(getattr(settings, 'marketplace_redis_timeout_seconds', 1.0)))
        _REDIS = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=timeout,
            socket_timeout=timeout,
        )
    return _REDIS


async def _redis_command(awaitable):
    settings = get_settings()
    timeout = max(0.05, float(getattr(settings, 'marketplace_redis_timeout_seconds', 1.0)))
    try:
        return await asyncio.wait_for(awaitable, timeout=timeout)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        raise MarketplaceLimiterUnavailable('Shared marketplace limiter is unavailable') from exc


async def _redis_wait(key: str, interval: float) -> None:
    settings = get_settings()
    try:
        redis = await _redis_client()
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        if isinstance(exc, MarketplaceLimiterUnavailable):
            raise
        raise MarketplaceLimiterUnavailable('Shared marketplace limiter is unavailable') from exc
    redis_key = f'{settings.redis_key_prefix}:rate:{key}'
    ttl_ms = max(1, int(interval * 1000))
    # SET NX PX is atomic across API/worker replicas. We wait for the remaining
    # TTL and retry instead of maintaining process-local timing state.
    max_wait = max(0.0, float(getattr(settings, 'marketplace_limiter_max_wait_seconds', 5.0)))
    deadline = time.monotonic() + max_wait
    while True:
        acquired = await _redis_command(redis.set(redis_key, '1', nx=True, px=ttl_ms))
        if acquired:
            return
        remaining = await _redis_command(redis.pttl(redis_key))
        delay = max(0.01, (remaining if remaining and remaining > 0 else ttl_ms) / 1000.0)
        budget = deadline - time.monotonic()
        if delay > budget:
            raise MarketplaceQuotaExceeded(delay)
        await asyncio.sleep(delay)


async def record_marketplace_backoff(
    marketplace: str,
    token: str,
    endpoint_group: str,
    *,
    retry_after_seconds: float,
) -> None:
    """Publish a provider 429 cooldown, then stop this logical operation."""
    settings = get_settings()
    delay = max(1.0, min(
        float(retry_after_seconds),
        float(getattr(settings, 'marketplace_retry_after_max_seconds', 900)),
    ))
    key = limiter_key(marketplace, token, endpoint_group)
    backend = settings.marketplace_limiter_backend.strip().lower()
    if backend == 'redis':
        try:
            redis = await _redis_client()
            redis_key = f'{settings.redis_key_prefix}:rate:{key}'
            ttl_ms = max(1, int(delay * 1000))
            script = """
            local current = redis.call('pttl', KEYS[1])
            if current < tonumber(ARGV[1]) then
              redis.call('psetex', KEYS[1], ARGV[1], '1')
              return tonumber(ARGV[1])
            end
            return current
            """
            if hasattr(redis, 'eval'):
                await _redis_command(redis.eval(script, 1, redis_key, ttl_ms))
            else:
                await _redis_command(redis.set(redis_key, '1', px=ttl_ms))
        except asyncio.CancelledError:
            raise
        except MarketplaceLimiterUnavailable:
            raise
        except Exception as exc:
            raise MarketplaceLimiterUnavailable('Shared marketplace limiter is unavailable') from exc
    elif backend == 'memory':
        bucket = _BUCKETS.setdefault(key, _Bucket(asyncio.Lock()))
        async with bucket.lock:
            bucket.next_at = max(bucket.next_at, time.monotonic() + delay)
    else:
        raise RuntimeError(f'Unsupported marketplace limiter backend: {backend}')
    raise MarketplaceQuotaExceeded(delay)


def retry_after_seconds(response, default: float = 1.0) -> float:
    raw = str(response.headers.get('Retry-After') or '').strip()
    try:
        return max(1.0, float(raw))
    except (TypeError, ValueError):
        try:
            parsed = parsedate_to_datetime(raw)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return max(1.0, (parsed - datetime.now(timezone.utc)).total_seconds())
        except (TypeError, ValueError, OverflowError):
            return max(1.0, float(default))


async def raise_for_marketplace_status(response, marketplace: str, token: str, endpoint_group: str) -> None:
    if getattr(response, 'status_code', 200) == 429:
        await record_marketplace_backoff(
            marketplace,
            token,
            endpoint_group,
            retry_after_seconds=retry_after_seconds(response),
        )
    response.raise_for_status()


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
