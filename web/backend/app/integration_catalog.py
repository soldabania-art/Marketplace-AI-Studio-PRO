"""Versioned Integration Hub catalog. Availability is deny-by-default."""

CATALOG_VERSION = "2026-09-10.1"

PRODUCTION_GATES = ("auth", "read", "reconciliation", "rate_limits", "recovery", "audit")

CONNECTORS = (
    {"code": "wildberries", "name": "Wildberries", "kind": "marketplace", "stage": "read_beta", "capabilities": ("catalog", "stocks", "sales", "finance", "advertising", "feedbacks", "content_write"), "next_gate": "End-to-end reconciliation on production seller accounts"},
    {"code": "ozon", "name": "Ozon", "kind": "marketplace", "stage": "planned", "capabilities": ("catalog", "stocks", "sales", "finance", "advertising", "feedbacks"), "next_gate": "Read-only adapter and sandbox contract tests"},
    {"code": "yandex_market", "name": "Яндекс Маркет", "kind": "marketplace", "stage": "planned", "capabilities": ("catalog", "stocks", "sales", "finance", "feedbacks"), "next_gate": "Read-only adapter after Ozon vertical"},
    {"code": "kaspi", "name": "Kaspi.kz", "kind": "marketplace", "stage": "discovery", "capabilities": ("catalog", "stocks", "sales", "finance", "feedbacks", "cross_border"), "next_gate": "API and Merchant of Record legal validation"},
    {"code": "uzum", "name": "Uzum Market", "kind": "marketplace", "stage": "planned", "capabilities": ("catalog", "stocks", "sales", "finance", "feedbacks", "localization", "cross_border"), "next_gate": "API, localization and partner validation"},
    {"code": "csv", "name": "CSV / Excel export", "kind": "accounting", "stage": "available", "capabilities": ("costs_import", "saved_mapping", "validation"), "next_gate": "Expand canonical entities beyond cost data"},
    {"code": "1c", "name": "1С", "kind": "accounting", "stage": "planned", "capabilities": ("catalog", "warehouses", "stocks", "orders", "costs", "documents"), "next_gate": "OData read-only reference adapter"},
    {"code": "moysklad", "name": "МойСклад", "kind": "accounting", "stage": "planned", "capabilities": ("catalog", "warehouses", "stocks", "orders", "costs", "webhooks"), "next_gate": "Read-only JSON API adapter"},
    {"code": "saby", "name": "Saby / СБИС", "kind": "accounting", "stage": "planned", "capabilities": ("catalog", "stocks", "documents"), "next_gate": "Customer demand and API contract"},
    {"code": "kontur", "name": "Контур", "kind": "accounting", "stage": "planned", "capabilities": ("documents", "compliance"), "next_gate": "Product-specific API scope"},
    {"code": "warehouse_api", "name": "Склады и фулфилмент", "kind": "logistics", "stage": "planned", "capabilities": ("warehouses", "stocks", "reservations", "shipments", "returns", "webhooks"), "next_gate": "Partner adapter SDK and pilot"},
)


def public_catalog(connected_codes=()) -> dict:
    connected = set(connected_codes)
    items = []
    for definition in CONNECTORS:
        item = {key: list(value) if isinstance(value, tuple) else value for key, value in definition.items()}
        item["connected"] = definition["code"] in connected
        item["production_ready"] = definition["stage"] == "available"
        item["gates"] = list(PRODUCTION_GATES)
        items.append(item)
    return {"catalog_version": CATALOG_VERSION, "connectors": items}
