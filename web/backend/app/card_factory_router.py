import hashlib
import json
from io import BytesIO
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .ai_card_factory import build_fact_set, generate_grounded_copy, generate_product_visual
from .ai_generation_service import begin_generation, complete_generation, fail_generation, public_generation, stable_hash
from .billing_service import require_entitlement
from .config import get_settings
from .db import get_db
from .marketplace_connections import decrypt_connection
from .marketplace_sync import latest_snapshot
from .models import AIGeneration, CardPublication, GenerationStatus, MarketplaceConnection, MediaPublication, PublicationStatus, User
from .security import get_current_user
from .store_access import require_store_admin, resolve_store
from .trial_service import ensure_ai_access, refund_trial_card, reserve_trial_card
from .wb_content import build_card_update, fetch_wb_card, update_wb_card, upload_wb_media_file

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


class PreparePublicationRequest(GenerateCardRequest):
    generation_id: str = Field(min_length=36, max_length=36)


class ConfirmPublicationRequest(BaseModel):
    store_id: str = Field(min_length=1, max_length=36)
    payload_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    confirmation: str = Field(min_length=1, max_length=40)


class VerifyPublicationRequest(BaseModel):
    store_id: str = Field(min_length=1, max_length=36)


class PrepareMediaPublicationRequest(GenerateCardRequest):
    generation_id: str = Field(min_length=36, max_length=36)


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


def _connection(db: Session, store_id: str) -> MarketplaceConnection:
    connection = db.query(MarketplaceConnection).filter(
        MarketplaceConnection.store_id == store_id,
        MarketplaceConnection.marketplace == "wildberries",
        MarketplaceConnection.enabled.is_(True),
    ).first()
    if not connection:
        raise HTTPException(409, "Wildberries не подключён к выбранному магазину.")
    return connection


def _publication_payload(row: CardPublication) -> dict:
    return {
        "id": row.id,
        "generation_id": row.generation_id,
        "store_id": row.store_id,
        "nm_id": int(row.subject_id),
        "marketplace": row.marketplace,
        "status": row.status.value,
        "payload_sha256": row.payload_sha256,
        "diff": row.diff_payload,
        "attempt_count": row.attempt_count,
        "verification_status": getattr(row, "verification_status", "not_checked"),
        "verification": getattr(row, "verification_payload", {}) or {},
        "verification_attempt_count": getattr(row, "verification_attempt_count", 0),
        "last_verified_at": getattr(row, "last_verified_at", None),
        "verified_at": getattr(row, "verified_at", None),
        "error": row.error,
        "approved_at": row.approved_at,
        "submitted_at": row.submitted_at,
        "created_at": row.created_at,
    }


def _find_card(cards: list[dict], nm_id: int) -> dict | None:
    return next((item for item in cards if int(item.get("nm_id") or 0) == nm_id), None)


def _verification_result(publication: CardPublication, live: dict) -> tuple[str, dict]:
    proposed = publication.proposed_payload or {}
    source = publication.source_payload or {}
    fields = {
        field: {
            "expected": str(proposed.get(field) or ""),
            "actual": str(live.get(field) or ""),
            "matches": str(live.get(field) or "") == str(proposed.get(field) or ""),
        }
        for field in ("title", "description")
    }
    if all(item["matches"] for item in fields.values()):
        status = "applied"
    elif all(str(live.get(field) or "") == str(source.get(field) or "") for field in fields):
        status = "pending"
    else:
        status = "mismatch"
    return status, {"fields": fields, "live_card_updated_at": live.get("updated_at")}


def _photo_urls(card: dict) -> list[str]:
    return [str(photo.get("big") or "") for photo in (card.get("photos") or []) if photo.get("big")]


def _media_publication_payload(row: MediaPublication) -> dict:
    asset = row.asset_payload or {}
    return {
        "id": row.id,
        "generation_id": row.generation_id,
        "store_id": row.store_id,
        "nm_id": int(row.subject_id),
        "marketplace": row.marketplace,
        "status": row.status.value,
        "payload_sha256": row.payload_sha256,
        "diff": row.diff_payload,
        "asset": {key: asset.get(key) for key in ("url", "sha256", "content_type", "bytes")},
        "attempt_count": row.attempt_count,
        "verification_status": row.verification_status,
        "verification": row.verification_payload or {},
        "verification_attempt_count": row.verification_attempt_count,
        "last_verified_at": row.last_verified_at,
        "verified_at": row.verified_at,
        "error": row.error,
        "approved_at": row.approved_at,
        "submitted_at": row.submitted_at,
        "created_at": row.created_at,
    }


def _media_verification_result(publication: MediaPublication, live: dict) -> tuple[str, dict]:
    source_urls = list((publication.source_payload or {}).get("photo_urls") or [])
    live_urls = _photo_urls(live)
    target_position = int((publication.diff_payload or {}).get("target_position") or (len(source_urls) + 1))
    prefix_matches = live_urls[:len(source_urls)] == source_urls
    if prefix_matches and len(live_urls) >= target_position:
        status = "applied"
    elif live_urls == source_urls:
        status = "pending"
    else:
        status = "mismatch"
    return status, {
        "source_photo_count": len(source_urls),
        "live_photo_count": len(live_urls),
        "target_position": target_position,
        "existing_photos_unchanged": prefix_matches,
        "live_card_updated_at": live.get("updated_at"),
    }


async def _download_and_validate_asset(asset: dict) -> tuple[bytes, str, dict]:
    parsed = urlparse(str(asset.get("url") or ""))
    if parsed.scheme != "https" or not (parsed.hostname or "").endswith(".blob.vercel-storage.com"):
        raise HTTPException(409, "Сохранённый визуал находится вне защищённого хранилища TROVENDI.")
    async with httpx.AsyncClient(timeout=45.0, follow_redirects=False) as client:
        response = await client.get(str(asset["url"]))
    response.raise_for_status()
    raw = response.content
    if not raw or len(raw) > 32_000_000:
        raise HTTPException(422, "Изображение должно быть меньше 32 МБ.")
    expected_sha256 = str(asset.get("sha256") or "")
    if not expected_sha256 or hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise HTTPException(409, "Сохранённый визуал изменился после подготовки публикации.")
    try:
        with Image.open(BytesIO(raw)) as image:
            image_format = str(image.format or "").upper()
            width, height = image.size
            image.verify()
    except (UnidentifiedImageError, OSError) as exc:
        raise HTTPException(422, "Файл не является корректным изображением.") from exc
    if image_format not in {"WEBP", "JPEG", "PNG", "BMP", "GIF"}:
        raise HTTPException(422, "Формат изображения не поддерживается Wildberries.")
    if width < 700 or height < 900:
        raise HTTPException(422, "Wildberries требует изображение не меньше 700×900 пикселей.")
    content_type = {"WEBP": "image/webp", "JPEG": "image/jpeg", "PNG": "image/png", "BMP": "image/bmp", "GIF": "image/gif"}[image_format]
    return raw, content_type, {"width": width, "height": height, "format": image_format}


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
    require_entitlement(db, store.workspace_id, "card_visual_generation")
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


@router.post("/publications/prepare", status_code=201)
def prepare_publication(payload: PreparePublicationRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    store = _resolve_connected_store(db, user, payload.store_id)
    require_entitlement(db, store.workspace_id, "marketplace_publication")
    source, snapshot = _load_card(db, store.id, payload.nm_id)
    fact_set = build_fact_set(source)
    generation = db.query(AIGeneration).filter(
        AIGeneration.id == payload.generation_id,
        AIGeneration.store_id == store.id,
        AIGeneration.feature == "card_factory_copy",
        AIGeneration.subject_id == str(payload.nm_id),
        AIGeneration.status == GenerationStatus.completed,
    ).first()
    if not generation:
        raise HTTPException(404, "Сохранённая текстовая версия карточки не найдена.")
    if generation.fact_set_sha256 != fact_set["sha256"]:
        raise HTTPException(409, "Каталог изменился после генерации. Создайте новую AI-версию перед публикацией.")
    result = generation.result_payload or {}
    try:
        proposed = build_card_update(source, title=result.get("wb_title") or "", description=result.get("description") or "")
        current = build_card_update(source, title=source.get("title") or "", description=source.get("description") or "")
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    diff = {
        "title": {"before": current["title"], "after": proposed["title"], "changed": current["title"] != proposed["title"]},
        "description": {"before": current["description"], "after": proposed["description"], "changed": current["description"] != proposed["description"]},
        "unchanged_fields": ["brand", "dimensions", "characteristics", "sizes", "barcodes"],
        "catalog_snapshot_created_at": snapshot.created_at.isoformat() if snapshot.created_at else None,
    }
    if not diff["title"]["changed"] and not diff["description"]["changed"]:
        raise HTTPException(409, "AI-версия не отличается от текущей карточки WB.")
    payload_sha256 = stable_hash(proposed)
    existing = db.query(CardPublication).filter(
        CardPublication.store_id == store.id,
        CardPublication.generation_id == generation.id,
        CardPublication.payload_sha256 == payload_sha256,
        CardPublication.status == PublicationStatus.prepared,
    ).order_by(CardPublication.created_at.desc()).first()
    if existing:
        return _publication_payload(existing)
    publication = CardPublication(
        workspace_id=store.workspace_id,
        store_id=store.id,
        user_id=user.id,
        generation_id=generation.id,
        subject_id=str(payload.nm_id),
        fact_set_sha256=fact_set["sha256"],
        source_card_sha256=stable_hash(current),
        payload_sha256=payload_sha256,
        source_payload=current,
        proposed_payload=proposed,
        diff_payload=diff,
        status=PublicationStatus.prepared,
    )
    db.add(publication)
    db.commit()
    db.refresh(publication)
    return _publication_payload(publication)


@router.post("/publications/{publication_id}/publish")
async def publish_card(publication_id: str, payload: ConfirmPublicationRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    store = _resolve_connected_store(db, user, payload.store_id)
    require_entitlement(db, store.workspace_id, "marketplace_publication")
    require_store_admin(db, user, store)
    publication = db.query(CardPublication).filter(
        CardPublication.id == publication_id,
        CardPublication.store_id == store.id,
    ).with_for_update().first()
    if not publication:
        raise HTTPException(404, "Подготовленная публикация не найдена.")
    if publication.status == PublicationStatus.submitted:
        return _publication_payload(publication)
    if publication.status == PublicationStatus.submitting:
        raise HTTPException(409, "Эта версия уже отправляется в Wildberries.")
    if publication.status == PublicationStatus.stale:
        raise HTTPException(409, "Карточка WB изменилась. Подготовьте новую проверку перед публикацией.")
    if payload.payload_sha256 != publication.payload_sha256:
        raise HTTPException(409, "Подтверждение относится к другой версии карточки.")
    if payload.confirmation.strip().upper() != "ОПУБЛИКОВАТЬ":
        raise HTTPException(422, "Для публикации введите слово ОПУБЛИКОВАТЬ.")

    connection = _connection(db, store.id)
    token = decrypt_connection(connection)
    try:
        source = publication.source_payload or {}
        live = await fetch_wb_card(token, nm_id=int(publication.subject_id), vendor_code=source.get("vendorCode") or "")
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code if exc.response is not None else 502
        if status in {401, 403}:
            raise HTTPException(409, "WB отклонил токен. Переподключите магазин с правом редактирования контента.") from exc
        if status == 429:
            raise HTTPException(429, "WB ограничил частоту проверки карточки. Повторите позже.") from exc
        raise HTTPException(502, "Не удалось получить свежую карточку из WB.") from exc
    except httpx.RequestError as exc:
        raise HTTPException(502, "Не удалось связаться с WB для контрольной проверки.") from exc
    if not live:
        publication.status = PublicationStatus.stale
        publication.error = "Карточка отсутствует в свежем ответе WB."
        db.commit()
        raise HTTPException(409, publication.error)

    proposed = publication.proposed_payload or {}
    if live.get("title") == proposed.get("title") and live.get("description") == proposed.get("description"):
        now = datetime.now(timezone.utc)
        publication.status = PublicationStatus.submitted
        publication.provider_response = {"accepted": True, "already_applied": True}
        publication.submitted_at = now
        publication.verification_status = "applied"
        publication.verification_payload = _verification_result(publication, live)[1]
        publication.verification_attempt_count += 1
        publication.last_verified_at = now
        publication.verified_at = now
        publication.error = ""
        db.commit()
        return _publication_payload(publication)
    try:
        live_current = build_card_update(live, title=live.get("title") or "", description=live.get("description") or "")
    except ValueError as exc:
        publication.status = PublicationStatus.stale
        publication.error = f"Свежая карточка WB неполная: {exc}"
        db.commit()
        raise HTTPException(409, publication.error) from exc
    if build_fact_set(live)["sha256"] != publication.fact_set_sha256 or stable_hash(live_current) != publication.source_card_sha256:
        publication.status = PublicationStatus.stale
        publication.error = "Карточка WB изменилась после подготовки. AI-версия не отправлена."
        db.commit()
        raise HTTPException(409, publication.error)

    publication.status = PublicationStatus.submitting
    publication.approved_at = datetime.now(timezone.utc)
    publication.attempt_count += 1
    publication.error = ""
    db.commit()
    try:
        response = await update_wb_card(token, proposed)
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code if exc.response is not None else 502
        publication.status = PublicationStatus.failed
        publication.error = f"WB отклонил обновление карточки (HTTP {status})."
        db.commit()
        if status in {401, 403}:
            raise HTTPException(409, "Токен WB не разрешает редактировать контент магазина.") from exc
        if status == 429:
            raise HTTPException(429, "WB ограничил частоту публикаций. Повторите позже.") from exc
        raise HTTPException(502, publication.error) from exc
    except httpx.RequestError as exc:
        publication.status = PublicationStatus.failed
        publication.error = "Ответ WB не получен. Перед повтором карточка будет проверена заново."
        db.commit()
        raise HTTPException(502, publication.error) from exc
    publication.status = PublicationStatus.submitted
    publication.provider_response = response
    publication.submitted_at = datetime.now(timezone.utc)
    publication.verification_status = "pending"
    publication.verification_payload = {}
    publication.error = ""
    db.commit()
    return _publication_payload(publication)


@router.post("/publications/{publication_id}/verify")
async def verify_publication(publication_id: str, payload: VerifyPublicationRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    store = _resolve_connected_store(db, user, payload.store_id)
    publication = db.query(CardPublication).filter(
        CardPublication.id == publication_id,
        CardPublication.store_id == store.id,
    ).with_for_update().first()
    if not publication:
        raise HTTPException(404, "Публикация не найдена в выбранном магазине.")
    if publication.status != PublicationStatus.submitted:
        raise HTTPException(409, "Сначала отправьте подтверждённую версию в Wildberries.")

    connection = _connection(db, store.id)
    token = decrypt_connection(connection)
    now = datetime.now(timezone.utc)
    publication.verification_attempt_count += 1
    publication.last_verified_at = now
    try:
        source = publication.source_payload or {}
        live = await fetch_wb_card(token, nm_id=int(publication.subject_id), vendor_code=source.get("vendorCode") or "")
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code if exc.response is not None else 502
        publication.verification_status = "error"
        publication.verification_payload = {"message": "WB не разрешил контрольное чтение карточки.", "status_code": status}
        db.commit()
        if status in {401, 403}:
            raise HTTPException(409, "WB отклонил токен. Переподключите магазин.") from exc
        if status == 429:
            raise HTTPException(429, "WB ограничил частоту проверок. Повторите позже.") from exc
        raise HTTPException(502, "Не удалось проверить карточку после публикации.") from exc
    except httpx.RequestError as exc:
        publication.verification_status = "error"
        publication.verification_payload = {"message": "WB временно недоступен для контрольного чтения."}
        db.commit()
        raise HTTPException(502, "Не удалось связаться с WB для проверки публикации.") from exc

    if not live:
        publication.verification_status = "mismatch"
        publication.verification_payload = {"message": "Карточка отсутствует в свежем ответе WB."}
    else:
        status, result = _verification_result(publication, live)
        publication.verification_status = status
        publication.verification_payload = result
        if status == "applied":
            publication.verified_at = now
    db.commit()
    db.refresh(publication)
    return _publication_payload(publication)


@router.get("/publications")
def publications(store_id: str, nm_id: int | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    store = resolve_store(db, user, store_id)
    query = db.query(CardPublication).filter(CardPublication.store_id == store.id)
    if nm_id:
        query = query.filter(CardPublication.subject_id == str(nm_id))
    rows = query.order_by(CardPublication.created_at.desc()).limit(30).all()
    return {"items": [_publication_payload(row) for row in rows]}


@router.post("/media-publications/prepare", status_code=201)
def prepare_media_publication(payload: PrepareMediaPublicationRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    store = _resolve_connected_store(db, user, payload.store_id)
    require_entitlement(db, store.workspace_id, "marketplace_publication")
    source, snapshot = _load_card(db, store.id, payload.nm_id)
    fact_set = build_fact_set(source)
    generation = db.query(AIGeneration).filter(
        AIGeneration.id == payload.generation_id,
        AIGeneration.store_id == store.id,
        AIGeneration.feature == "card_factory_visual",
        AIGeneration.subject_id == str(payload.nm_id),
        AIGeneration.status == GenerationStatus.completed,
    ).first()
    if not generation:
        raise HTTPException(404, "Сохранённая версия изображения не найдена.")
    asset = generation.result_payload or {}
    if asset.get("storage_status") != "stored" or not asset.get("url") or not asset.get("sha256"):
        raise HTTPException(409, "Сначала сохраните AI-визуал в постоянном хранилище.")
    if generation.fact_set_sha256 != fact_set["sha256"]:
        raise HTTPException(409, "Карточка изменилась после генерации визуала. Создайте новую версию.")
    source_urls = _photo_urls(source)
    if len(source_urls) >= 30:
        raise HTTPException(409, "В карточке уже 30 изображений — это предел Wildberries.")
    source_payload = {"nm_id": payload.nm_id, "vendor_code": source.get("vendor_code") or "", "photo_urls": source_urls}
    proposed = {"generation_id": generation.id, "asset_sha256": asset["sha256"], "target_position": len(source_urls) + 1}
    payload_sha256 = stable_hash(proposed)
    existing = db.query(MediaPublication).filter(
        MediaPublication.store_id == store.id,
        MediaPublication.generation_id == generation.id,
        MediaPublication.payload_sha256 == payload_sha256,
        MediaPublication.status == PublicationStatus.prepared,
    ).order_by(MediaPublication.created_at.desc()).first()
    if existing:
        return _media_publication_payload(existing)
    publication = MediaPublication(
        workspace_id=store.workspace_id,
        store_id=store.id,
        user_id=user.id,
        generation_id=generation.id,
        subject_id=str(payload.nm_id),
        fact_set_sha256=fact_set["sha256"],
        source_card_sha256=stable_hash(source_payload),
        payload_sha256=payload_sha256,
        source_payload=source_payload,
        asset_payload={key: asset.get(key) for key in ("url", "pathname", "sha256", "content_type", "bytes")},
        diff_payload={
            "before_photo_count": len(source_urls),
            "after_photo_count": len(source_urls) + 1,
            "target_position": len(source_urls) + 1,
            "existing_photos_unchanged": True,
            "catalog_snapshot_created_at": snapshot.created_at.isoformat() if snapshot.created_at else None,
        },
        status=PublicationStatus.prepared,
    )
    db.add(publication)
    db.commit()
    db.refresh(publication)
    return _media_publication_payload(publication)


@router.post("/media-publications/{publication_id}/publish")
async def publish_media(publication_id: str, payload: ConfirmPublicationRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    store = _resolve_connected_store(db, user, payload.store_id)
    require_entitlement(db, store.workspace_id, "marketplace_publication")
    require_store_admin(db, user, store)
    publication = db.query(MediaPublication).filter(
        MediaPublication.id == publication_id,
        MediaPublication.store_id == store.id,
    ).with_for_update().first()
    if not publication:
        raise HTTPException(404, "Подготовленная публикация изображения не найдена.")
    if publication.status == PublicationStatus.submitted:
        return _media_publication_payload(publication)
    if publication.status == PublicationStatus.submitting:
        raise HTTPException(409, "Это изображение уже отправляется в Wildberries.")
    if publication.status == PublicationStatus.stale:
        raise HTTPException(409, "Набор изображений WB изменился. Подготовьте проверку заново.")
    if payload.payload_sha256 != publication.payload_sha256:
        raise HTTPException(409, "Подтверждение относится к другой версии изображения.")
    if payload.confirmation.strip().upper() != "ОПУБЛИКОВАТЬ ФОТО":
        raise HTTPException(422, "Для публикации введите ОПУБЛИКОВАТЬ ФОТО.")

    connection = _connection(db, store.id)
    token = decrypt_connection(connection)
    source = publication.source_payload or {}
    try:
        live = await fetch_wb_card(token, nm_id=int(publication.subject_id), vendor_code=source.get("vendor_code") or "")
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code if exc.response is not None else 502
        if status in {401, 403}:
            raise HTTPException(409, "WB-токен не разрешает редактировать медиа карточки.") from exc
        if status == 429:
            raise HTTPException(429, "WB ограничил частоту проверки. Повторите позже.") from exc
        raise HTTPException(502, "Не удалось получить свежую карточку WB.") from exc
    except httpx.RequestError as exc:
        raise HTTPException(502, "Не удалось связаться с WB для контрольной проверки.") from exc
    if not live or _photo_urls(live) != list(source.get("photo_urls") or []):
        publication.status = PublicationStatus.stale
        publication.error = "Фотографии карточки изменились после подготовки. Отправка заблокирована."
        db.commit()
        raise HTTPException(409, publication.error)

    try:
        raw, content_type, dimensions = await _download_and_validate_asset(publication.asset_payload or {})
    except httpx.HTTPError as exc:
        raise HTTPException(502, "Не удалось получить сохранённый визуал TROVENDI.") from exc
    publication.status = PublicationStatus.submitting
    publication.attempt_count += 1
    publication.approved_at = datetime.now(timezone.utc)
    db.commit()
    try:
        response = await upload_wb_media_file(
            token,
            nm_id=int(publication.subject_id),
            photo_number=int((publication.diff_payload or {}).get("target_position") or 1),
            raw=raw,
            content_type=content_type,
        )
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code if exc.response is not None else 502
        publication.status = PublicationStatus.failed
        publication.error = f"WB отклонил изображение (HTTP {status})."
        db.commit()
        if status in {401, 403}:
            raise HTTPException(409, "WB-токен не разрешает загрузку медиа.") from exc
        if status == 429:
            raise HTTPException(429, "WB ограничил частоту загрузок. Повторите позже.") from exc
        raise HTTPException(502, publication.error) from exc
    except httpx.RequestError as exc:
        publication.status = PublicationStatus.failed
        publication.error = "Ответ WB не получен. Автоматическая повторная загрузка отключена."
        db.commit()
        raise HTTPException(502, publication.error) from exc
    except ValueError as exc:
        publication.status = PublicationStatus.failed
        publication.error = f"WB отклонил изображение: {str(exc)[:500]}"
        db.commit()
        raise HTTPException(502, publication.error) from exc
    publication.status = PublicationStatus.submitted
    publication.provider_response = {**response, "validated_image": dimensions}
    publication.submitted_at = datetime.now(timezone.utc)
    publication.verification_status = "pending"
    publication.verification_payload = {}
    publication.error = ""
    db.commit()
    return _media_publication_payload(publication)


@router.post("/media-publications/{publication_id}/verify")
async def verify_media_publication(publication_id: str, payload: VerifyPublicationRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    store = _resolve_connected_store(db, user, payload.store_id)
    publication = db.query(MediaPublication).filter(
        MediaPublication.id == publication_id,
        MediaPublication.store_id == store.id,
    ).with_for_update().first()
    if not publication:
        raise HTTPException(404, "Публикация изображения не найдена.")
    if publication.status != PublicationStatus.submitted:
        raise HTTPException(409, "Сначала отправьте подтверждённое изображение в Wildberries.")
    token = decrypt_connection(_connection(db, store.id))
    now = datetime.now(timezone.utc)
    publication.verification_attempt_count += 1
    publication.last_verified_at = now
    try:
        source = publication.source_payload or {}
        live = await fetch_wb_card(token, nm_id=int(publication.subject_id), vendor_code=source.get("vendor_code") or "")
    except httpx.HTTPStatusError as exc:
        publication.verification_status = "error"
        publication.verification_payload = {"message": "WB не разрешил контрольное чтение карточки."}
        db.commit()
        status = exc.response.status_code if exc.response is not None else 502
        raise HTTPException(429 if status == 429 else 502, "Не удалось проверить изображение в WB.") from exc
    except httpx.RequestError as exc:
        publication.verification_status = "error"
        publication.verification_payload = {"message": "WB временно недоступен для контрольного чтения."}
        db.commit()
        raise HTTPException(502, "Не удалось проверить изображение в WB.") from exc
    if not live:
        status, result = "mismatch", {"message": "Карточка отсутствует в свежем ответе WB."}
    else:
        status, result = _media_verification_result(publication, live)
    publication.verification_status = status
    publication.verification_payload = result
    if status == "applied":
        publication.verified_at = now
    db.commit()
    db.refresh(publication)
    return _media_publication_payload(publication)


@router.get("/media-publications")
def media_publications(store_id: str, nm_id: int | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    store = resolve_store(db, user, store_id)
    query = db.query(MediaPublication).filter(MediaPublication.store_id == store.id)
    if nm_id:
        query = query.filter(MediaPublication.subject_id == str(nm_id))
    rows = query.order_by(MediaPublication.created_at.desc()).limit(30).all()
    return {"items": [_media_publication_payload(row) for row in rows]}
