"""WB01 regression tests: source capability checks are bounded and credential-fenced."""
from __future__ import annotations

import asyncio
from datetime import date

import httpx
import pytest

from app import rate_limit
from app.wb_capability_preflight import (
    PREFLIGHT_REQUEST_TIMEOUT_SECONDS,
    PREFLIGHT_TOTAL_TIMEOUT_SECONDS,
    check_wb_capabilities,
)


TOKEN = "candidate-token-that-must-never-leak"
ALLOWED_READ_REQUESTS = {
    ("POST", "/content/v2/get/cards/list"),
    ("POST", "/api/analytics/v1/stocks-report/wb-warehouses"),
    ("POST", "/api/analytics/v3/sales-funnel/products/history"),
    ("POST", "/api/finance/v1/sales-reports/detailed"),
    ("GET", "/adv/v1/promotion/count"),
    ("GET", "/adv/v3/fullstats"),
    ("GET", "/api/v1/feedbacks"),
}


def test_preflight_budget_fits_inside_existing_ten_second_proxy_ceiling():
    assert PREFLIGHT_TOTAL_TIMEOUT_SECONDS == 8.0
    assert PREFLIGHT_REQUEST_TIMEOUT_SECONDS == 2.0


def run_check(handler, monkeypatch):
    limiter_calls = []

    async def no_wait(marketplace, token, endpoint_group, **kwargs):
        limiter_calls.append((marketplace, token, endpoint_group))

    monkeypatch.setattr(rate_limit, "wait_marketplace_slot", no_wait)
    result = asyncio.run(check_wb_capabilities(
        TOKEN,
        transport=httpx.MockTransport(handler),
        today=date(2026, 9, 13),
    ))
    return result, limiter_calls


def endpoint_rows(result):
    return {
        endpoint["key"]: endpoint
        for source in result["sources"]
        for endpoint in source["endpoints"]
    }


def test_full_access_uses_only_bounded_read_contracts(monkeypatch):
    requests = []

    def handler(request):
        requests.append(request)
        assert request.headers["authorization"] == TOKEN
        if request.url.path == "/content/v2/get/cards/list":
            assert request.method == "POST"
            assert request.read().count(b'"limit":1') == 1
            return httpx.Response(200, json={"cards": [{"nmID": 101}], "cursor": {"total": 1}})
        if request.url.path == "/api/analytics/v1/stocks-report/wb-warehouses":
            assert b'"limit":1' in request.read()
            return httpx.Response(204)
        if request.url.path == "/api/analytics/v3/sales-funnel/products/history":
            assert b'"nmIds":[101]' in request.read()
            return httpx.Response(200, json={"data": {"products": []}})
        if request.url.path == "/api/finance/v1/sales-reports/detailed":
            body = request.read()
            assert b'"limit":1' in body
            assert b'"dateFrom":"2026-09-13"' in body
            assert b'"dateTo":"2026-09-13"' in body
            return httpx.Response(204)
        if request.url.path == "/adv/v1/promotion/count":
            return httpx.Response(200, json={"adverts": [{"advert_list": [{"advertId": 77}]}]})
        if request.url.path == "/adv/v3/fullstats":
            assert request.url.params["ids"] == "77"
            assert request.url.params["beginDate"] == "2026-09-13"
            assert request.url.params["endDate"] == "2026-09-13"
            return httpx.Response(200, json=[])
        if request.url.path == "/api/v1/feedbacks":
            assert dict(request.url.params) == {"isAnswered": "false", "take": "1", "skip": "0"}
            return httpx.Response(200, json={"data": {"feedbacks": []}})
        raise AssertionError(f"unexpected provider request: {request.method} {request.url}")

    result, limiter_calls = run_check(handler, monkeypatch)
    assert result["summary"] == "complete"
    assert result["authentication_error"] is False
    assert result["requests_made"] == 7
    assert all(row["status"] == "available" for row in endpoint_rows(result).values())
    assert {(request.method, request.url.path) for request in requests} == ALLOWED_READ_REQUESTS
    assert len(limiter_calls) == len(requests)
    assert all(call[0] == "wildberries" and call[1] == TOKEN for call in limiter_calls)
    assert TOKEN not in str(result)


@pytest.mark.parametrize("status_code,authentication_error", [(401, True), (403, False)])
def test_unauthorized_and_forbidden_are_distinct_without_exposing_response_body(
    monkeypatch, status_code, authentication_error,
):
    def handler(request):
        if request.url.path == "/content/v2/get/cards/list":
            return httpx.Response(status_code, json={"detail": f"rejected {TOKEN}"})
        return httpx.Response(503, json={"detail": "later"})

    result, _ = run_check(handler, monkeypatch)
    catalog = endpoint_rows(result)["catalog.cards"]
    assert catalog["status"] == "forbidden"
    assert catalog["authentication_error"] is authentication_error
    assert result["authentication_error"] is authentication_error
    assert TOKEN not in str(result)


def test_partial_access_does_not_hide_the_failed_endpoint(monkeypatch):
    def handler(request):
        if request.url.path == "/content/v2/get/cards/list":
            return httpx.Response(200, json={"cards": [{"nmID": 101}]})
        if request.url.path == "/api/analytics/v1/stocks-report/wb-warehouses":
            return httpx.Response(200, json={"data": []})
        if request.url.path == "/api/analytics/v3/sales-funnel/products/history":
            return httpx.Response(403, json={"detail": "category denied"})
        if request.url.path == "/adv/v1/promotion/count":
            return httpx.Response(200, json={"adverts": []})
        return httpx.Response(204)

    result, _ = run_check(handler, monkeypatch)
    analytics = next(source for source in result["sources"] if source["key"] == "analytics")
    assert analytics["status"] == "forbidden"
    assert {row["key"]: row["status"] for row in analytics["endpoints"]} == {
        "analytics.stocks": "available",
        "analytics.sales": "forbidden",
    }
    advertising = next(source for source in result["sources"] if source["key"] == "advertising")
    assert advertising["status"] == "unchecked"
    assert endpoint_rows(result)["advertising.statistics"]["reason"] == "no_campaigns"
    assert result["summary"] == "partial"


def test_retry_after_5xx_and_timeout_are_transient_and_bounded(monkeypatch):
    backoffs = []

    async def no_wait(*args, **kwargs):
        return None

    async def record_backoff(marketplace, token, endpoint_group, *, retry_after_seconds):
        backoffs.append((marketplace, token, endpoint_group, retry_after_seconds))
        raise rate_limit.MarketplaceQuotaExceeded(retry_after_seconds)

    monkeypatch.setattr(rate_limit, "wait_marketplace_slot", no_wait)
    monkeypatch.setattr(rate_limit, "record_marketplace_backoff", record_backoff)

    def handler(request):
        if request.url.path == "/content/v2/get/cards/list":
            return httpx.Response(429, headers={"Retry-After": "17"})
        if request.url.path == "/api/analytics/v1/stocks-report/wb-warehouses":
            return httpx.Response(503, json={"detail": "later"})
        if request.url.path == "/api/v1/feedbacks":
            raise httpx.ReadTimeout(f"timeout with {TOKEN}", request=request)
        return httpx.Response(503, json={"detail": "later"})

    result = asyncio.run(check_wb_capabilities(
        TOKEN,
        transport=httpx.MockTransport(handler),
        today=date(2026, 9, 13),
    ))
    rows = endpoint_rows(result)
    assert rows["catalog.cards"]["status"] == "transient_error"
    assert rows["catalog.cards"]["retry_after_seconds"] == 17
    assert rows["analytics.stocks"]["status"] == "transient_error"
    assert rows["feedbacks.list"]["status"] == "transient_error"
    assert result["summary"] == "temporary_failure"
    assert backoffs == [("wildberries", TOKEN, "preflight-content-cards", 17.0)]
    assert result["requests_made"] <= 7
    assert TOKEN not in str(result)
