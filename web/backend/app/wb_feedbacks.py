"""Privacy-minimised, read-only Wildberries feedback reader."""

import httpx

from .rate_limit import raise_for_marketplace_status, wait_marketplace_slot

WB_FEEDBACKS_URL = "https://feedbacks-api.wildberries.ru/api/v1/feedbacks"


def normalize_feedback(row: dict) -> dict | None:
    """Keep business facts only; buyer identity and contact data are discarded."""
    feedback_id = str(row.get("id") or "").strip()
    product = row.get("productDetails") if isinstance(row.get("productDetails"), dict) else {}
    nm_id = product.get("nmId")
    if not feedback_id or nm_id is None:
        return None
    answer = row.get("answer") if isinstance(row.get("answer"), dict) else {}
    rating = max(1, min(5, int(row.get("productValuation") or 1)))
    return {
        "feedback_id": feedback_id,
        "nm_id": int(nm_id),
        "vendor_code": str(product.get("supplierArticle") or "")[:160],
        "product_name": str(product.get("productName") or "")[:500],
        "rating": rating,
        "text": str(row.get("text") or "")[:5000],
        "pros": str(row.get("pros") or "")[:3000],
        "cons": str(row.get("cons") or "")[:3000],
        "created_at": row.get("createdDate"),
        "answered": bool(answer.get("text") or row.get("isAnswered")),
        "answer_text": str(answer.get("text") or "")[:5000],
        "answer_created_at": answer.get("createDate"),
    }


def normalize_feedback_page(payload) -> tuple[list[dict], int | None]:
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        return [], None
    rows = []
    for raw in data.get("feedbacks") or []:
        if not isinstance(raw, dict):
            continue
        item = normalize_feedback(raw)
        if item:
            rows.append(item)
    unanswered = data.get("countUnanswered")
    return rows, int(unanswered) if unanswered is not None else None


async def fetch_wb_feedbacks(token: str, *, max_items: int = 5000) -> tuple[list[dict], int | None]:
    """Fetch a bounded snapshot. This module never performs reply/write operations."""
    take = min(1000, max(1, int(max_items)))
    result: list[dict] = []
    unanswered_count = None
    async with httpx.AsyncClient(timeout=45.0) as client:
        for answered in (False, True):
            skip = 0
            while len(result) < max_items:
                await wait_marketplace_slot("wildberries", token, "feedbacks-read", min_interval_seconds=1)
                response = await client.get(
                    WB_FEEDBACKS_URL,
                    params={"isAnswered": str(answered).lower(), "take": take, "skip": skip},
                    headers={"Authorization": token},
                )
                await raise_for_marketplace_status(response, 'wildberries', token, 'feedbacks-read')
                body = response.json()
                raw_data = body.get("data") if isinstance(body, dict) else None
                raw_count = len(raw_data.get("feedbacks") or []) if isinstance(raw_data, dict) else 0
                page, count = normalize_feedback_page(body)
                if not answered and unanswered_count is None:
                    unanswered_count = count
                result.extend(page)
                skip += raw_count
                if raw_count < take:
                    break
    return result[:max_items], unanswered_count
