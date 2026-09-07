"""Marketplace API rate limiting.

The abstraction is intentionally provider-neutral. Development/single-worker uses
an in-process limiter. Production can switch to Redis/Upstash without changing
WB/Ozon callers. Keys must be hashes/fingerprints, never plaintext API tokens.
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

def token_fingerprint(token: str) -> str:
    return hashlib.sha256(token.encode('utf-8')).hexdigest()[:24]

def limiter_key(marketplace: str, token: str, endpoint_group: str) -> str:
    return f'{marketplace}:{token_fingerprint(token)}:{endpoint_group}'

async def wait_marketplace_slot(marketplace: str, token: str, endpoint_group: str, *, min_interval_seconds: float | None = None) -> None:
    settings = get_settings()
    interval = settings.marketplace_default_min_interval_seconds if min_interval_seconds is None else min_interval_seconds
    interval = max(0.0, float(interval))
    key = limiter_key(marketplace, token, endpoint_group)
    bucket = _BUCKETS.setdefault(key, _Bucket(asyncio.Lock()))
    async with bucket.lock:
        now = time.monotonic()
        delay = max(0.0, bucket.next_at - now)
        if delay:
            await asyncio.sleep(delay)
        bucket.next_at = time.monotonic() + interval
