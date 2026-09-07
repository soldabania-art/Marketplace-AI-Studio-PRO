"""Wildberries Analytics API readers used by Smart FBO.

Only current official Analytics endpoints are used here. Marketplace tokens are
never logged or persisted by this module. Rate limiting is scoped by token and
endpoint group.
"""
from collections import defaultdict
from datetime import date, timedelta

import httpx

from .rate_limit import wait_marketplace_slot

WB_ANALYTICS_BASE = 'https://seller-analytics-api.wildberries.ru'
WB_STOCKS_URL = f'{WB_ANALYTICS_BASE}/api/analytics/v1/stocks-report/wb-warehouses'
WB_FUNNEL_HISTORY_URL = f'{WB_ANALYTICS_BASE}/api/analytics/v3/sales-funnel/products/history'


def _rows(payload):
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    data = payload.get('data')
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get('items'), list):
        return data['items']
    return []


def normalize_stock_rows(payload) -> list[dict]:
    result = []
    for row in _rows(payload):
        nm_id = row.get('nmId')
        warehouse_id = row.get('warehouseId')
        if nm_id is None or warehouse_id is None:
            continue
        result.append({
            'nm_id': int(nm_id),
            'chrt_id': row.get('chrtId'),
            'warehouse_id': int(warehouse_id),
            'warehouse_name': row.get('warehouseName') or 'Склад WB',
            'region_name': row.get('regionName') or '',
            'quantity': max(0, int(row.get('quantity') or 0)),
            'in_way_to_client': max(0, int(row.get('inWayToClient') or 0)),
            'in_way_from_client': max(0, int(row.get('inWayFromClient') or 0)),
        })
    return result


def normalize_sales_history(payload, period_days: int) -> dict[int, dict]:
    days = max(1, int(period_days))
    result = {}
    for row in _rows(payload):
        product = row.get('product') or {}
        nm_id = product.get('nmId')
        if nm_id is None:
            continue
        history = row.get('history') or []
        orders = sum(max(0, int(day.get('orderCount') or 0)) for day in history if isinstance(day, dict))
        buyouts = sum(max(0, int(day.get('buyoutCount') or 0)) for day in history if isinstance(day, dict))
        result[int(nm_id)] = {
            'nm_id': int(nm_id),
            'vendor_code': product.get('vendorCode') or '',
            'title': product.get('title') or '',
            'orders': orders,
            'buyouts': buyouts,
            'period_days': days,
            'avg_daily_orders': round(orders / days, 4),
        }
    return result


async def fetch_wb_current_stocks(token: str, nm_ids: list[int] | None = None) -> list[dict]:
    offset = 0
    limit = 250000
    result: list[dict] = []
    for _ in range(10):
        await wait_marketplace_slot('wildberries', token, 'analytics-stocks', min_interval_seconds=20)
        body = {'nmIds': list(nm_ids or []), 'chrtIds': [], 'limit': limit, 'offset': offset}
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(WB_STOCKS_URL, json=body, headers={'Authorization': token})
        response.raise_for_status()
        page = normalize_stock_rows(response.json())
        result.extend(page)
        if len(page) < limit:
            break
        offset += limit
    return result


async def fetch_wb_sales_velocity(token: str, period_days: int = 7, nm_ids: list[int] | None = None) -> dict[int, dict]:
    days = min(7, max(1, int(period_days)))
    end = date.today()
    start = end - timedelta(days=days - 1)
    await wait_marketplace_slot('wildberries', token, 'analytics-sales-funnel-history', min_interval_seconds=20)
    body = {
        'selectedPeriod': {'start': start.isoformat(), 'end': end.isoformat()},
        'nmIds': list(nm_ids or []),
        'skipDeletedNm': True,
        'aggregationLevel': 'day',
    }
    async with httpx.AsyncClient(timeout=45.0) as client:
        response = await client.post(WB_FUNNEL_HISTORY_URL, json=body, headers={'Authorization': token})
    response.raise_for_status()
    return normalize_sales_history(response.json(), days)


def build_network_supply_inputs(stocks: list[dict], sales: dict[int, dict]) -> list[dict]:
    stock_by_nm: dict[int, int] = defaultdict(int)
    warehouses_by_nm: dict[int, list[dict]] = defaultdict(list)
    for row in stocks:
        nm_id = int(row['nm_id'])
        stock_by_nm[nm_id] += max(0, int(row.get('quantity') or 0))
        warehouses_by_nm[nm_id].append(row)

    rows = []
    for nm_id, metric in sales.items():
        rows.append({
            'nm_id': nm_id,
            'sku': str(metric.get('vendor_code') or nm_id),
            'title': metric.get('title') or '',
            'stock': stock_by_nm.get(nm_id, 0),
            'avg_daily_sales': float(metric.get('avg_daily_orders') or 0),
            'orders_period': int(metric.get('orders') or 0),
            'period_days': int(metric.get('period_days') or 7),
            'warehouse_stocks': sorted(warehouses_by_nm.get(nm_id, []), key=lambda x: (-x['quantity'], x['warehouse_name'])),
        })
    return rows
