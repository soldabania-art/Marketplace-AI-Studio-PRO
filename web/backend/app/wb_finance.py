"""Wildberries realization report reader for the auditable Profit Center ledger.

Uses the current Finance API. Monetary strings are converted to integer kopecks;
the original source row is preserved by the caller for audit and reprocessing.
"""
import hashlib
import json
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

import httpx

from .rate_limit import wait_marketplace_slot

WB_SALES_REPORT_URL = 'https://finance-api.wildberries.ru/api/finance/v1/sales-reports/detailed'


def _value(row: dict, *names, default=None):
    for name in names:
        if row.get(name) is not None:
            return row[name]
    return default


def _kopecks(row: dict, *names) -> int:
    value = _value(row, *names, default='0')
    try:
        return int((Decimal(str(value).replace(',', '.')) * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    except (InvalidOperation, TypeError, ValueError):
        return 0


def _integer(row: dict, *names) -> int:
    value = _value(row, *names, default=0)
    try:
        return int(Decimal(str(value).replace(',', '.')))
    except (InvalidOperation, TypeError, ValueError):
        return 0


def _rows(payload) -> list[dict]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if not isinstance(payload, dict):
        return []
    for candidate in (payload.get('data'), payload.get('rows'), payload.get('items'), payload.get('reportDetails')):
        if isinstance(candidate, list):
            return [row for row in candidate if isinstance(row, dict)]
        if isinstance(candidate, dict):
            for key in ('rows', 'items', 'reportDetails'):
                if isinstance(candidate.get(key), list):
                    return [row for row in candidate[key] if isinstance(row, dict)]
    return []


def normalize_financial_row(row: dict) -> dict | None:
    source_line_id = str(_value(row, 'rrdId', 'rrd_id', default='') or '')
    if not source_line_id:
        return None
    document_type = str(_value(row, 'docTypeName', 'doc_type_name', default='') or '')
    operation = str(_value(row, 'supplierOperName', 'supplier_oper_name', default='') or '')
    quantity = _integer(row, 'quantity')
    if quantity > 0 and ('возврат' in document_type.lower() or 'return' in document_type.lower()):
        quantity = -quantity
    source_encoded = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
    nm_id = _integer(row, 'nmId', 'nm_id') or None
    return {
        'source_line_id': source_line_id,
        'report_id': str(_value(row, 'realizationReportId', 'realizationreportId', 'realizationreport_id', default='') or ''),
        'nm_id': nm_id,
        'vendor_code': str(_value(row, 'vendorCode', 'saName', 'sa_name', default='') or ''),
        'title': str(_value(row, 'title', 'subjectName', 'subject_name', default='') or ''),
        'operation': operation,
        'document_type': document_type,
        'event_date': str(_value(
            row,
            'saleDate', 'saleDt', 'sale_dt',
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


async def fetch_financial_report_page(token: str, *, date_from: str, date_to: str, rrd_id: int = 0) -> list[dict]:
    await wait_marketplace_slot('wildberries', token, 'finance-sales-report', min_interval_seconds=60.0)
    body = {'dateFrom': date_from, 'dateTo': date_to, 'rrdId': int(rrd_id)}
    async with httpx.AsyncClient(timeout=90.0) as client:
        response = await client.post(WB_SALES_REPORT_URL, json=body, headers={'Authorization': token})
    if response.status_code == 204:
        return []
    response.raise_for_status()
    payload = response.json() if response.content else []
    return [normalized for row in _rows(payload) if (normalized := normalize_financial_row(row))]
