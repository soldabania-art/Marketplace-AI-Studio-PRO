import httpx

from .rate_limit import wait_marketplace_slot

WB_ACCEPTANCE_URL = "https://common-api.wildberries.ru/api/tariffs/v1/acceptance/coefficients"


def normalize_wb_slots(rows: list[dict]) -> list[dict]:
    slots = []
    for row in rows:
        coefficient = row.get("coefficient")
        allowed = bool(row.get("allowUnload")) and coefficient in (0, 1)
        if not allowed:
            continue
        slots.append({
            "marketplace": "wildberries",
            "warehouse_id": row.get("warehouseID"),
            "warehouse_name": row.get("warehouseName") or "Склад WB",
            "date": row.get("date"),
            "coefficient": coefficient,
            "free_acceptance": coefficient == 0,
            "box_type_id": row.get("boxTypeID"),
            "is_sorting_center": bool(row.get("isSortingCenter")),
            "storage_coef": row.get("storageCoef"),
            "delivery_coef": row.get("deliveryCoef"),
        })
    return sorted(slots, key=lambda x: (x.get("date") or "", x.get("warehouse_name") or ""))


async def fetch_wb_slots(token: str, warehouse_ids: list[int] | None = None) -> list[dict]:
    params = {}
    if warehouse_ids:
        params["warehouseIDs"] = ",".join(str(x) for x in warehouse_ids)
    # Conservative default. Endpoint-specific official limits can override this
    # later without exposing or persisting the plaintext marketplace token.
    await wait_marketplace_slot("wildberries", token, "acceptance-coefficients")
    async with httpx.AsyncClient(timeout=12.0) as client:
        response = await client.get(WB_ACCEPTANCE_URL, params=params, headers={"Authorization": token})
        response.raise_for_status()
        return normalize_wb_slots(response.json())
