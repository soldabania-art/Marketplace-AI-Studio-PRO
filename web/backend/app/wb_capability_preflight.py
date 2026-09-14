"""Bounded, read-only capability probes for the WB sources used by TROVENDI.

The probes use the importers' real API surfaces and never persist response bodies.
POST denotes transport here; every operation below is documented by WB as a read.
"""
from __future__ import annotations

import asyncio
import time
from datetime import date, datetime, timezone
from typing import Any

import httpx

from . import rate_limit


# Keep the complete synchronous backend operation inside the existing 10 second
# frontend API ceiling. The proxy gets one additional second to receive and
# serialize the backend response.
PREFLIGHT_TOTAL_TIMEOUT_SECONDS = 8.0
PREFLIGHT_REQUEST_TIMEOUT_SECONDS = 2.0
PREFLIGHT_MAX_REQUESTS = 7

CATALOG_URL = "https://content-api.wildberries.ru/content/v2/get/cards/list"
STOCKS_URL = "https://seller-analytics-api.wildberries.ru/api/analytics/v1/stocks-report/wb-warehouses"
SALES_URL = "https://seller-analytics-api.wildberries.ru/api/analytics/v3/sales-funnel/products/history"
FINANCE_URL = "https://finance-api.wildberries.ru/api/finance/v1/sales-reports/detailed"
CAMPAIGNS_URL = "https://advert-api.wildberries.ru/adv/v1/promotion/count"
AD_STATS_URL = "https://advert-api.wildberries.ru/adv/v3/fullstats"
FEEDBACKS_URL = "https://feedbacks-api.wildberries.ru/api/v1/feedbacks"

SOURCE_DEFINITIONS = (
    ("catalog", "Каталог", ("catalog.cards",)),
    ("analytics", "Остатки и продажи", ("analytics.stocks", "analytics.sales")),
    ("finance", "Финансы", ("finance.report",)),
    ("advertising", "Реклама", ("advertising.campaigns", "advertising.statistics")),
    ("feedbacks", "Отзывы", ("feedbacks.list",)),
)


def unchecked_capabilities() -> dict[str, Any]:
    endpoints = {
        key: {"key": key, "status": "unchecked", "authentication_error": False, "reason": "not_checked"}
        for _, _, keys in SOURCE_DEFINITIONS for key in keys
    }
    return _result(endpoints, checked_at=None, requests_made=0)


def _safe_endpoint(
    key: str,
    status: str,
    *,
    authentication_error: bool = False,
    reason: str | None = None,
    retry_after_seconds: int | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "key": key,
        "status": status,
        "authentication_error": authentication_error,
    }
    if reason:
        row["reason"] = reason
    if retry_after_seconds is not None:
        row["retry_after_seconds"] = retry_after_seconds
    return row


def _source_status(rows: list[dict[str, Any]]) -> str:
    statuses = {row["status"] for row in rows}
    if statuses == {"available"}:
        return "available"
    if "forbidden" in statuses:
        return "forbidden"
    if "transient_error" in statuses:
        return "transient_error"
    return "unchecked"


def _result(endpoints: dict[str, dict[str, Any]], *, checked_at, requests_made: int) -> dict[str, Any]:
    sources = []
    all_rows = []
    for source_key, label, endpoint_keys in SOURCE_DEFINITIONS:
        rows = [endpoints[key] for key in endpoint_keys]
        all_rows.extend(rows)
        sources.append({
            "key": source_key,
            "label": label,
            "status": _source_status(rows),
            "endpoints": rows,
        })
    statuses = [row["status"] for row in all_rows]
    available = statuses.count("available")
    if available == len(statuses):
        summary = "complete"
    elif available:
        summary = "partial"
    elif "transient_error" in statuses:
        summary = "temporary_failure"
    elif "forbidden" in statuses:
        summary = "rejected"
    else:
        summary = "unchecked"
    return {
        "checked_at": checked_at,
        "summary": summary,
        "authentication_error": any(row["authentication_error"] for row in all_rows),
        "requests_made": requests_made,
        "sources": sources,
    }


def _first_nm_id(response: httpx.Response) -> int | None:
    try:
        payload = response.json()
        cards = payload.get("cards") if isinstance(payload, dict) else None
        value = cards[0].get("nmID") if isinstance(cards, list) and cards and isinstance(cards[0], dict) else None
        parsed = int(value)
        return parsed if parsed > 0 else None
    except (TypeError, ValueError, IndexError, AttributeError):
        return None


def _first_campaign_id(response: httpx.Response) -> int | None:
    try:
        payload = response.json()
        for group in payload.get("adverts", []):
            for item in group.get("advert_list", []):
                parsed = int(item.get("advertId"))
                if parsed > 0:
                    return parsed
    except (TypeError, ValueError, AttributeError):
        return None
    return None


async def check_wb_capabilities(
    token: str,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    """Check all first-import sources using at most seven bounded provider calls."""
    token = token.strip()
    day = today or date.today()
    day_text = day.isoformat()
    deadline = time.monotonic() + PREFLIGHT_TOTAL_TIMEOUT_SECONDS
    endpoints: dict[str, dict[str, Any]] = {}
    requests_made = 0

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(PREFLIGHT_REQUEST_TIMEOUT_SECONDS),
        transport=transport,
        follow_redirects=False,
    ) as client:
        async def probe(key: str, method: str, url: str, endpoint_group: str, **kwargs):
            nonlocal requests_made
            if requests_made >= PREFLIGHT_MAX_REQUESTS:
                return _safe_endpoint(key, "unchecked", reason="request_limit") , None
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return _safe_endpoint(key, "transient_error", reason="preflight_timeout"), None

            async def perform():
                nonlocal requests_made
                await rate_limit.wait_marketplace_slot(
                    "wildberries", token, endpoint_group,
                    min_interval_seconds=kwargs.pop("min_interval_seconds", 0.0),
                )
                requests_made += 1
                return await client.request(method, url, headers={"Authorization": token}, **kwargs)

            try:
                response = await asyncio.wait_for(
                    perform(), timeout=min(PREFLIGHT_REQUEST_TIMEOUT_SECONDS, remaining),
                )
                if response.status_code == 429:
                    retry = rate_limit.retry_after_seconds(response)
                    try:
                        await rate_limit.record_marketplace_backoff(
                            "wildberries", token, endpoint_group, retry_after_seconds=retry,
                        )
                    except rate_limit.MarketplaceQuotaExceeded as exc:
                        return _safe_endpoint(
                            key, "transient_error", reason="rate_limited",
                            retry_after_seconds=exc.retry_after_seconds,
                        ), response
                if response.status_code == 401:
                    return _safe_endpoint(key, "forbidden", authentication_error=True, reason="authentication_rejected"), response
                if response.status_code in {402, 403}:
                    return _safe_endpoint(key, "forbidden", reason="access_denied"), response
                if response.status_code >= 500:
                    return _safe_endpoint(key, "transient_error", reason="provider_unavailable"), response
                if response.status_code in {200, 204}:
                    return _safe_endpoint(key, "available"), response
                return _safe_endpoint(key, "unchecked", reason="probe_not_accepted"), response
            except rate_limit.MarketplaceQuotaExceeded as exc:
                return _safe_endpoint(
                    key, "transient_error", reason="rate_limited",
                    retry_after_seconds=exc.retry_after_seconds,
                ), None
            except rate_limit.MarketplaceLimiterUnavailable:
                return _safe_endpoint(key, "transient_error", reason="limiter_unavailable"), None
            except (httpx.RequestError, asyncio.TimeoutError):
                return _safe_endpoint(key, "transient_error", reason="network_error"), None

        catalog, catalog_response = await probe(
            "catalog.cards", "POST", CATALOG_URL, "preflight-content-cards",
            json={"settings": {"sort": {"ascending": True}, "filter": {"withPhoto": -1}, "cursor": {"limit": 1}}},
            min_interval_seconds=0.6,
        )
        endpoints[catalog["key"]] = catalog
        nm_id = _first_nm_id(catalog_response) if catalog["status"] == "available" and catalog_response else None

        stocks, _ = await probe(
            "analytics.stocks", "POST", STOCKS_URL, "preflight-analytics-stocks",
            json={"nmIds": [], "chrtIds": [], "limit": 1, "offset": 0},
            min_interval_seconds=20.0,
        )
        endpoints[stocks["key"]] = stocks
        if nm_id is None:
            endpoints["analytics.sales"] = _safe_endpoint(
                "analytics.sales", "unchecked", reason="no_catalog_item",
            )
        else:
            sales, _ = await probe(
                "analytics.sales", "POST", SALES_URL, "preflight-analytics-sales",
                json={
                    "selectedPeriod": {"start": day_text, "end": day_text},
                    "nmIds": [nm_id], "skipDeletedNm": True, "aggregationLevel": "day",
                },
                min_interval_seconds=20.0,
            )
            endpoints[sales["key"]] = sales

        finance, _ = await probe(
            "finance.report", "POST", FINANCE_URL, "preflight-finance-report",
            json={"dateFrom": day_text, "dateTo": day_text, "limit": 1, "rrdId": 0},
            min_interval_seconds=60.0,
        )
        endpoints[finance["key"]] = finance

        campaigns, campaign_response = await probe(
            "advertising.campaigns", "GET", CAMPAIGNS_URL, "preflight-advertising-campaigns",
            min_interval_seconds=0.2,
        )
        endpoints[campaigns["key"]] = campaigns
        campaign_id = _first_campaign_id(campaign_response) if campaigns["status"] == "available" and campaign_response else None
        if campaign_id is None:
            endpoints["advertising.statistics"] = _safe_endpoint(
                "advertising.statistics", "unchecked", reason="no_campaigns",
            )
        else:
            stats, _ = await probe(
                "advertising.statistics", "GET", AD_STATS_URL, "preflight-advertising-statistics",
                params={"ids": str(campaign_id), "beginDate": day_text, "endDate": day_text},
                min_interval_seconds=20.0,
            )
            endpoints[stats["key"]] = stats

        feedbacks, _ = await probe(
            "feedbacks.list", "GET", FEEDBACKS_URL, "preflight-feedbacks",
            params={"isAnswered": "false", "take": 1, "skip": 0},
            min_interval_seconds=1.0,
        )
        endpoints[feedbacks["key"]] = feedbacks

    return _result(
        endpoints,
        checked_at=datetime.now(timezone.utc).isoformat(),
        requests_made=requests_made,
    )
