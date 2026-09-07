import json

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .ai_card_factory import build_fact_set, generate_grounded_copy
from .db import get_db
from .marketplace_sync import latest_snapshot
from .models import MarketplaceConnection, User
from .security import get_current_user
from .store_access import resolve_store

router = APIRouter(prefix="/card-factory", tags=["card-factory"])


class GenerateCardRequest(BaseModel):
    store_id: str = Field(min_length=1, max_length=36)
    nm_id: int = Field(gt=0)


def _load_card(db: Session, store_id: str, nm_id: int) -> tuple[dict, object]:
    snapshot = latest_snapshot(db, store_id=store_id, marketplace="wildberries", snapshot_type="catalog")
    if not snapshot:
        raise HTTPException(409, "Каталог WB ещё не синхронизирован для выбранного магазина.")
    for card in (snapshot.payload or {}).get("items") or []:
        if int(card.get("nm_id") or 0) == nm_id:
            return card, snapshot
    raise HTTPException(404, "Карточка с таким nmId не найдена в каталоге выбранного магазина.")


def _resolve_connected_store(db: Session, user: User, store_id: str):
    store = resolve_store(db, user, store_id)
    connection = db.query(MarketplaceConnection).filter(
        MarketplaceConnection.store_id == store.id,
        MarketplaceConnection.marketplace == "wildberries",
        MarketplaceConnection.enabled.is_(True),
    ).first()
    if not connection:
        raise HTTPException(409, "Wildberries не подключён к выбранному магазину.")
    return store


@router.get("/cards/{nm_id}")
def card(nm_id: int, store_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    store = _resolve_connected_store(db, user, store_id)
    source, snapshot = _load_card(db, store.id, nm_id)
    fact_set = build_fact_set(source)
    return {
        "store_id": store.id,
        "store_name": store.name,
        "card": source,
        "fact_set": fact_set,
        "catalog_snapshot_created_at": snapshot.created_at,
    }


@router.post("/generate")
def generate(payload: GenerateCardRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    store = _resolve_connected_store(db, user, payload.store_id)
    source, snapshot = _load_card(db, store.id, payload.nm_id)
    fact_set = build_fact_set(source)
    try:
        draft = generate_grounded_copy(fact_set)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(502, f"AI не прошёл проверку фактов: {exc}") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(502, "AI-сервис временно не ответил. Попробуйте ещё раз.") from exc
    return {
        "store_id": store.id,
        "nm_id": payload.nm_id,
        "fact_set_sha256": fact_set["sha256"],
        "catalog_snapshot_created_at": snapshot.created_at,
        "draft": draft,
        "publish_requires_confirmation": True,
    }
