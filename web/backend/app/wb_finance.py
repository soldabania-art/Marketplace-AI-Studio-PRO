"""Wildberries realization report reader for the auditable Profit Center ledger.

Uses the current Finance API. Monetary strings are converted to integer kopecks;
the original source row is preserved by the caller for audit and reprocessing.
"""
import hashlib
import json
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

import httpx

from .rate_limit import wait_marketplace_slot
from .marketplace_page import MarketplacePageResult

WB_SALES_REPORT_URL = 'https://finance-api.wildberries.ru/api/finance/v1/sales-reports/detailed'
SCHEMA_SOURCE_URL = 'https://dev.wildberries.ru/docs/openapi/financial-reports-and-accounting'


def _value(row: dict, *names, default=None):
    for name in names:
        if row.get(name) is not None:
            return row[name]
    return default


def _decimal(row: dict, *names) -> Decimal | None:
    value = _value(row, *names)
    if value is None or value == '':
        return None
    try:
        result = Decimal(str(value).replace(',', '.'))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"invalid numeric field {names[0]}") from exc
    if not result.is_finite():
        raise ValueError(f"non-finite numeric field {names[0]}")
    return result


def _kopecks(row: dict, *names) -> int:
    value = _decimal(row, *names)
    if value is None:
        return 0
    return int((value * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def _integer(row: dict, *names) -> int:
    value = _decimal(row, *names)
    if value is None:
        return 0
    if value != value.to_integral_value():
        raise ValueError(f"non-integral field {names[0]}")
    return int(value)


def normalize_financial_row(row: dict) -> dict:
    source_line_id = _integer(row, 'rrdId', 'rrd_id')
    if source_line_id <= 0:
        raise ValueError('missing or invalid rrdId')
    document_type = str(_value(row, 'docTypeName', 'doc_type_name', default='') or '')
    operation = str(_value(row, 'supplierOperName', 'supplier_oper_name', default='') or '')
    quantity = _integer(row, 'quantity')
    if quantity > 0 and ('возврат' in document_type.lower() or 'return' in document_type.lower()):
        quantity = -quantity
    source_encoded = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
    nm_id = _integer(row, 'nmId', 'nm_id') or None
    return {
        'source_line_id': str(source_line_id),
        'report_id': str(_value(row, 'reportId', 'realizationReportId', 'realizationreportId', 'realizationreport_id', default='') or ''),
        'nm_id': nm_id,
        'vendor_code': str(_value(row, 'vendorCode', 'saName', 'sa_name', default='') or ''),
        'title': str(_value(row, 'title', 'subjectName', 'subject_name', default='') or ''),
        'operation': operation,
        'document_type': document_type,
        'event_date': str(_value(
            row,
            'saleDate', 'saleDt', 'sale_dt', 'rrDate',
            'rrDt', 'rr_dt',
            'reportDate', 'report_date', 'createDate', 'create_date',
            default='',
        ) or ''),
        'quantity': quantity,
        'gross_kopecks': _kopecks(row, 'retailAmount', 'retail_amount'),
        'payout_kopecks': _kopecks(row, 'forPay', 'ppvzForPay', 'ppvz_for_pay'),
        'commission_kopecks': _kopecks(row, 'salesCommission', 'ppvzSalesCommission', 'ppvz_sales_commission'),
        'logistics_kopecks': _kopecks(row, 'deliveryRub', 'delivery_rub') + _kopecks(row, 'rebillLogisticCost', 'rebill_logistic_cost'),
        'acquiring_kopecks': _kopecks(row, 'acquiringFee', 'acquiring_fee'),
        'storage_kopecks': _kopecks(row, 'storageFee', 'storage_fee'),
        'acceptance_kopecks': _kopecks(row, 'acceptance'),
        'penalty_kopecks': _kopecks(row, 'penalty'),
        'deduction_kopecks': _kopecks(row, 'deduction'),
        'additional_payment_kopecks': _kopecks(row, 'additionalPayment', 'additional_payment'),
        'source_sha256': hashlib.sha256(source_encoded).hexdigest(),
        'source_payload': row,
    }


def parse_financial_report_page(payload, *, status_code: int = 200) -> MarketplacePageResult:
    if status_code == 204:
        return MarketplacePageResult([], 0, 0, 0, None, 'documented_empty')
    if not isinstance(payload, list):
        return MarketplacePageResult([], 0, 0, 0, None, 'unknown', [{
            'code': 'unknown_schema', 'expected': 'JSON array for HTTP 200', 'actual': type(payload).__name__,
        }])
    if not payload:
        return MarketplacePageResult([], 0, 0, 0, None, 'unknown', [{
            'code': 'undocumented_empty_200', 'expected': 'HTTP 204 for no data',
        }])
    items = []
    evidence = []
    for index, row in enumerate(payload):
        if not isinstance(row, dict):
            evidence.append({'code': 'invalid_row_type', 'row': index, 'actual': type(row).__name__})
            continue
        try:
            items.append(normalize_financial_row(row))
        except (ValueError, InvalidOperation) as exc:
            evidence.append({'code': 'rejected_row', 'row': index, 'reason': str(exc)[:200]})
    rejected = len(payload) - len(items)
    cursor = int(items[-1]['source_line_id']) if items else None
    return MarketplacePageResult(
        items, len(payload), len(items), rejected, cursor,
        'partial' if rejected else 'valid', evidence,
    )


async def fetch_financial_report_page(token: str, *, date_from: str, date_to: str, rrd_id: int = 0) -> MarketplacePageResult:
    await wait_marketplace_slot('wildberries', token, 'finance-sales-report', min_interval_seconds=60.0)
    body = {'dateFrom': date_from, 'dateTo': date_to, 'rrdId': int(rrd_id)}
    async with httpx.AsyncClient(timeout=90.0) as client:
        response = await client.post(WB_SALES_REPORT_URL, json=body, headers={'Authorization': token})
    if response.status_code == 204:
        return parse_financial_report_page(None, status_code=204)
    response.raise_for_status()
    payload = response.json() if response.content else None
    return parse_financial_report_page(payload, status_code=response.status_code)
