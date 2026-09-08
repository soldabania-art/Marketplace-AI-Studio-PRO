import json
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .ai_card_factory import build_fact_set, generate_grounded_copy, generate_product_visual
from .ai_generation_service import begin_generation, complete_generation, fail_generation, public_generation
from .config import get_settings
from .db import get_db
from .marketplace_sync import latest_snapshot
from .models import AIGeneration, GenerationStatus, MarketplaceConnection, User
from .security import get_current_user
from .store_access import resolve_store
from .trial_service import ensure_ai_access, refund_trial_card, reserve_trial_card

router = APIRouter(prefix="/card-factory", tags=["card-factory"])


class GenerateCardRequest(BaseModel):
    store_id: str = Field(min_length=1, max_length=36)
    nm_id: int = Field(gt=0)


class GenerateVisualRequest(GenerateCardRequest):
    visual_index: int = Field(default=0, ge=0, le=7)


class FinalizeVisualRequest(BaseModel):
    store_id: str = Field(min_length=1, max_length=36)
    generation_id: str = Field(min_length=36, max_length=36)
    url: str = Field(min_length=20, max_length=2048)
    pathname: str = Field(min_length=10, max_length=1024)
    content_type: str = Field(pattern=r"^image/webp$")
    bytes: int = Field(gt=0, le=15_000_000)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


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
    previous = db.query(AIGeneration).filter(AIGeneration.store_id == store.id, AIGeneration.feature == "card_factory_copy", AIGeneration.subject_id == str(payload.nm_id), AIGeneration.status == GenerationStatus.completed).first()
    trial_started_now = False
    if previous:
        ensure_ai_access(db, store.workspace_id, allow_exhausted=True)
    else:
        _, trial_started_now = reserve_trial_card(db, store.workspace_id)
    generation = None
    completed = False
    try:
        generation = begin_generation(db, store=store, user=user, feature="card_factory_copy", subject_id=str(payload.nm_id), input_payload=fact_set, fact_set_sha256=fact_set["sha256"])
        draft = generate_grounded_copy(fact_set)
        metadata = draft.pop("_generation_metadata", {})
        complete_generation(db, generation, draft, metadata)
        completed = True
    except RuntimeError as exc:
        if generation:
            fail_generation(db, generation, exc)
        raise HTTPException(503, str(exc)) from exc
    except (ValueError, json.JSONDecodeError) as exc:
        if generation:
            fail_generation(db, generation, exc)
        raise HTTPException(502, f"AI не прошёл проверку фактов: {exc}") from exc
    except httpx.HTTPError as exc:
        if generation:
            fail_generation(db, generation, exc)
        raise HTTPException(502, "AI-сервис временно не ответил. Попробуйте ещё раз.") from exc
    except Exception as exc:
        if generation:
            fail_generation(db, generation, exc)
        raise
    finally:
        if not completed and not previous:
            refund_trial_card(db, store.workspace_id, trial_started_now)
    return {
        "generation_id": generation.id,
        "store_id": store.id,
        "nm_id": payload.nm_id,
        "fact_set_sha256": fact_set["sha256"],
        "catalog_snapshot_created_at": snapshot.created_at,
        "draft": draft,
        "publish_requires_confirmation": True,
    }


@router.post("/generate-visual")
def generate_visual(payload: GenerateVisualRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    store = _resolve_connected_store(db, user, payload.store_id)
    ensure_ai_access(db, store.workspace_id, allow_exhausted=True)
    source, snapshot = _load_card(db, store.id, payload.nm_id)
    fact_set = build_fact_set(source)
    copy = db.query(AIGeneration).filter(
        AIGeneration.store_id == store.id,
        AIGeneration.feature == "card_factory_copy",
        AIGeneration.subject_id == str(payload.nm_id),
        AIGeneration.fact_set_sha256 == fact_set["sha256"],
        AIGeneration.status == GenerationStatus.completed,
    ).order_by(AIGeneration.created_at.desc()).first()
    plan = (copy.result_payload or {}).get("visual_plan") if copy else None
    if not plan or payload.visual_index >= len(plan):
        raise HTTPException(409, "Сначала создайте актуальный текстовый черновик и визуальный план.")
    direction = str(plan[payload.visual_index])[:1000]
    generation = begin_generation(db, store=store, user=user, feature="card_factory_visual", subject_id=str(payload.nm_id), input_payload={"fact_set_sha256": fact_set["sha256"], "visual_direction": direction, "visual_index": payload.visual_index}, fact_set_sha256=fact_set["sha256"], model=get_settings().openai_image_model)
    try:
        image_base64, metadata, result = generate_product_visual(fact_set, direction)
        complete_generation(db, generation, result, metadata)
    except RuntimeError as exc:
        fail_generation(db, generation, exc)
        raise HTTPException(503, str(exc)) from exc
    except (ValueError, httpx.HTTPError) as exc:
        fail_generation(db, generation, exc)
        raise HTTPException(502, f"Не удалось безопасно создать изображение: {exc}") from exc
    return {"generation_id": generation.id, "image_base64": image_base64, "content_type": "image/webp", "catalog_snapshot_created_at": snapshot.created_at}


@router.post("/finalize-visual")
def finalize_visual(payload: FinalizeVisualRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    store = resolve_store(db, user, payload.store_id)
    generation = db.query(AIGeneration).filter(AIGeneration.id == payload.generation_id, AIGeneration.store_id == store.id, AIGeneration.feature == "card_factory_visual", AIGeneration.status == GenerationStatus.completed).first()
    if not generation:
        raise HTTPException(404, "Версия изображения не найдена в выбранном магазине.")
    parsed = urlparse(payload.url)
    if parsed.scheme != "https" or not (parsed.hostname or "").endswith(".blob.vercel-storage.com"):
        raise HTTPException(400, "Разрешено только настроенное Vercel Blob хранилище.")
    expected_prefix = f"ai-assets/{store.id}/{generation.subject_id}/"
    if not payload.pathname.startswith(expected_prefix):
        raise HTTPException(400, "Путь изображения не принадлежит выбранному товару.")
    result = dict(generation.result_payload or {})
    result.update({"storage_status": "stored", "url": payload.url, "pathname": payload.pathname, "content_type": payload.content_type, "bytes": payload.bytes, "sha256": payload.sha256})
    generation.result_payload = result
    db.commit()
    return {"generation": public_generation(generation), "publish_requires_confirmation": True}


@router.get("/generations/{generation_id}")
def generation(generation_id: str, store_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    store = resolve_store(db, user, store_id)
    item = db.query(AIGeneration).filter(AIGeneration.id == generation_id, AIGeneration.store_id == store.id).first()
    if not item:
        raise HTTPException(404, "AI-генерация не найдена в выбранном магазине.")
    return public_generation(item)


@router.get("/generations")
def generations(store_id: str, nm_id: int | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    store = resolve_store(db, user, store_id)
    query = db.query(AIGeneration).filter(AIGeneration.store_id == store.id, AIGeneration.feature.in_(["card_factory_copy", "card_factory_visual"]))
    if nm_id:
        query = query.filter(AIGeneration.subject_id == str(nm_id))
    items = query.order_by(AIGeneration.created_at.desc()).limit(50).all()
    return {"items": [public_generation(item) for item in items]}
