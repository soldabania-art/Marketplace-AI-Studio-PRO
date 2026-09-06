from fastapi import APIRouter

api_router = APIRouter()

DEMO_META = {
    "mode": "demo",
    "live_data": False,
    "message": "Marketplace connection is not active. Values are demonstration data only.",
}


@api_router.get("/dashboard")
def dashboard():
    return {
        "meta": DEMO_META,
        "kpis": {
            "revenue": 482640,
            "net_profit": 127430,
            "ad_spend": 41280,
            "orders": 327,
            "currency": "RUB",
        },
    }


@api_router.get("/profit")
def profit():
    return {
        "meta": DEMO_META,
        "period_days": 30,
        "net_profit": 1846320,
        "margin_percent": 26.4,
        "ad_ratio_percent": 9.1,
        "formula": "payout - cogs - sku_ad_spend",
    }


@api_router.get("/director")
def director():
    return {
        "meta": DEMO_META,
        "items": [
            {
                "id": "demo-loss-sku",
                "severity": "critical",
                "title": "SKU 18374629 уходит в убыток",
                "estimated_effect_rub_month": 9800,
                "action": "review_advertising",
                "external_write": False,
            },
            {
                "id": "demo-seo",
                "severity": "warning",
                "title": "У 6 карточек просело SEO",
                "estimated_effect": "+11–18% traffic",
                "action": "regenerate_seo",
                "external_write": False,
            },
        ],
    }


@api_router.get("/integrations/status")
def integration_status():
    return {
        "meta": DEMO_META,
        "wildberries": {"connected": False, "status": "not_configured"},
        "ozon": {"connected": False, "status": "not_configured"},
    }
