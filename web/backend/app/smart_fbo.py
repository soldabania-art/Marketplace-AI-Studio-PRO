"""Deterministic Smart FBO supply planning core.

No AI guesses are used here. Inputs must come from marketplace/store facts. The
engine returns calculation provenance so every recommendation can be explained.
"""
from dataclasses import dataclass
from math import ceil

@dataclass(frozen=True)
class SupplyInput:
    sku: str
    warehouse_id: int | None
    warehouse_name: str
    stock: int
    avg_daily_sales: float
    lead_time_days: int = 7
    target_cover_days: int = 21
    safety_days: int = 5
    acceptance_coefficient: int | None = None


def recommend_supply(item: SupplyInput) -> dict:
    sales=max(0.0,float(item.avg_daily_sales)); stock=max(0,int(item.stock))
    lead=max(0,int(item.lead_time_days)); target=max(1,int(item.target_cover_days)); safety=max(0,int(item.safety_days))
    reorder_point=ceil(sales*(lead+safety))
    target_stock=ceil(sales*(target+lead+safety))
    recommended=max(0,target_stock-stock)
    days_cover=round(stock/sales,1) if sales>0 else None
    if sales<=0: urgency='no_sales'
    elif stock<=reorder_point: urgency='critical'
    elif days_cover is not None and days_cover<target: urgency='soon'
    else: urgency='healthy'
    acceptance=item.acceptance_coefficient in (0,1)
    return {
        'sku':item.sku,'warehouse_id':item.warehouse_id,'warehouse_name':item.warehouse_name,
        'stock':stock,'avg_daily_sales':round(sales,3),'days_of_cover':days_cover,
        'reorder_point':reorder_point,'target_stock':target_stock,'recommended_qty':recommended,
        'urgency':urgency,'acceptance_coefficient':item.acceptance_coefficient,'acceptance_available':acceptance,
        'provenance':{
            'method':'deterministic_v1',
            'formula':'target_stock = avg_daily_sales * (target_cover_days + lead_time_days + safety_days); recommended_qty = max(0, target_stock - stock)',
            'lead_time_days':lead,'target_cover_days':target,'safety_days':safety,
        },
    }


def recommend_many(items:list[SupplyInput])->list[dict]:
    rank={'critical':0,'soon':1,'healthy':2,'no_sales':3}
    rows=[recommend_supply(item) for item in items]
    return sorted(rows,key=lambda x:(rank.get(x['urgency'],9),-x['recommended_qty'],x['sku']))
