import base64
import binascii
import hashlib
import hmac
import json
import re
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from .ai_card_factory import analyze_product_photo, generate_grounded_copy
from .config import get_settings
from .db import get_db
from .models import BeginnerProject, User
from .security import get_current_user
from .store_access import resolve_store

router = APIRouter(prefix="/beginner", tags=["beginner"])
DATA_URL = re.compile(r"^data:(image/(?:jpeg|png|webp));base64,([A-Za-z0-9+/=\s]+)$")


class PhotoAnalysisRequest(BaseModel):
    image_data_url: str = Field(min_length=100, max_length=12_000_000)


class ConfirmedFact(BaseModel):
    label: str = Field(min_length=1, max_length=160)
    value: str = Field(min_length=1, max_length=1000)


class BeginnerDraftRequest(BaseModel):
    analysis: dict
    analysis_signature: str = Field(min_length=64, max_length=64)
    confirmed_facts: list[ConfirmedFact] = Field(min_length=2, max_length=40)


class BeginnerEconomicsRequest(BaseModel):
    marketplace: Literal["wildberries", "ozon"]
    price: Decimal = Field(gt=0, le=10_000_000)
    cogs: Decimal = Field(ge=0, le=10_000_000)
    commission_percent: Decimal = Field(ge=0, le=100)
    logistics: Decimal = Field(ge=0, le=1_000_000)
    ads_per_order: Decimal = Field(default=Decimal("0"), ge=0, le=1_000_000)
    tax_percent: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    returns_reserve: Decimal = Field(default=Decimal("0"), ge=0, le=1_000_000)
    other_costs: Decimal = Field(default=Decimal("0"), ge=0, le=1_000_000)
    target_margin_percent: Decimal = Field(default=Decimal("15"), ge=0, lt=100)
    rates_confirmed_by_seller: bool


ProjectStage = Literal["facts", "card", "economics", "publish", "management"]


class BeginnerProjectCreate(BaseModel):
    store_id: str = Field(min_length=1, max_length=36)
    title: str = Field(default="Новый товар", min_length=1, max_length=160)
    stage: ProjectStage = "facts"
    state: dict = Field(default_factory=dict)

    @field_validator("state")
    @classmethod
    def validate_state_size(cls, value):
        if len(json.dumps(value, ensure_ascii=False)) > 250_000:
            raise ValueError("Состояние проекта слишком большое")
        return value


class BeginnerProjectPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=160)
    stage: ProjectStage | None = None
    state: dict | None = None

    @field_validator("state")
    @classmethod
    def validate_state_size(cls, value):
        if value is not None and len(json.dumps(value, ensure_ascii=False)) > 250_000:
            raise ValueError("Состояние проекта слишком большое")
        return value


def _analysis_bytes(analysis: dict) -> bytes:
    return json.dumps(analysis, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def sign_analysis(analysis: dict) -> str:
    return hmac.new(get_settings().jwt_secret.encode(), _analysis_bytes(analysis), hashlib.sha256).hexdigest()


def _verify_analysis(analysis: dict, signature: str) -> None:
    if not hmac.compare_digest(sign_analysis(analysis), signature):
        raise HTTPException(400, "Результат анализа фотографии изменён. Загрузите фото заново.")


def build_beginner_fact_set(analysis: dict, confirmed_facts: list[ConfirmedFact]) -> dict:
    facts = [
        {"id": f"seller.confirmed.{index}", "label": row.label.strip(), "value": row.value.strip()}
        for index, row in enumerate(confirmed_facts)
        if row.label.strip() and row.value.strip()
    ]
    canonical = {"schema_version": 1, "source": "beginner_confirmed_intake", "facts": facts}
    digest = hashlib.sha256(json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {**canonical, "sha256": digest, "photo_analysis_confidence": analysis.get("confidence")}


def _money(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def calculate_beginner_economics(payload: BeginnerEconomicsRequest) -> dict:
    if not payload.rates_confirmed_by_seller:
        raise HTTPException(400, "Подтвердите комиссию и логистику. Система не подставляет непроверенные тарифы.")
    hundred = Decimal("100")
    commission = payload.price * payload.commission_percent / hundred
    tax = payload.price * payload.tax_percent / hundred
    fixed_costs = payload.cogs + payload.logistics + payload.ads_per_order + payload.returns_reserve + payload.other_costs
    total_costs = fixed_costs + commission + tax
    profit = payload.price - total_costs
    margin_percent = profit / payload.price * hundred
    roi_percent = profit / payload.cogs * hundred if payload.cogs else None
    variable_rate = (payload.commission_percent + payload.tax_percent) / hundred
    break_even_price = fixed_costs / (Decimal("1") - variable_rate) if variable_rate < 1 else None
    target_rate = (payload.commission_percent + payload.tax_percent + payload.target_margin_percent) / hundred
    target_price = fixed_costs / (Decimal("1") - target_rate) if target_rate < 1 else None
    blockers = []
    if profit <= 0:
        blockers.append("Цена не покрывает все указанные расходы.")
    if margin_percent < payload.target_margin_percent:
        blockers.append(f"Маржа ниже цели {payload.target_margin_percent}%.")
    if break_even_price is None or target_price is None:
        blockers.append("Сумма комиссии, налога и целевой маржи не позволяет рассчитать безопасную цену.")
    return {
        "marketplace": payload.marketplace,
        "currency": "RUB",
        "source": "seller_confirmed_manual_rates",
        "price": _money(payload.price),
        "costs": {
            "cogs": _money(payload.cogs),
            "commission": _money(commission),
            "logistics": _money(payload.logistics),
            "ads_per_order": _money(payload.ads_per_order),
            "tax": _money(tax),
            "returns_reserve": _money(payload.returns_reserve),
            "other": _money(payload.other_costs),
            "total": _money(total_costs),
        },
        "profit_per_unit": _money(profit),
        "margin_percent": _money(margin_percent),
        "roi_percent": _money(roi_percent) if roi_percent is not None else None,
        "break_even_price": _money(break_even_price) if break_even_price is not None else None,
        "recommended_min_price": _money(target_price) if target_price is not None else None,
        "target_margin_percent": _money(payload.target_margin_percent),
        "safe_to_launch": not blockers,
        "blockers": blockers,
        "publish_requires_confirmation": True,
    }


def serialize_project(project: BeginnerProject) -> dict:
    return {
        "id": project.id,
        "store_id": project.store_id,
        "title": project.title,
        "stage": project.stage,
        "state": project.state or {},
        "created_at": project.created_at,
        "updated_at": project.updated_at,
    }


def accessible_project(db: Session, user: User, project_id: str) -> BeginnerProject:
    project = db.get(BeginnerProject, project_id)
    if project is None:
        raise HTTPException(404, "Товарный проект не найден.")
    resolve_store(db, user, project.store_id)
    return project


@router.post("/analyze-photo")
def analyze_photo(payload: PhotoAnalysisRequest, user: User = Depends(get_current_user)):
    match = DATA_URL.fullmatch(payload.image_data_url)
    if not match:
        raise HTTPException(400, "Поддерживаются фотографии JPG, PNG и WebP.")
    try:
        raw = base64.b64decode(match.group(2), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(400, "Файл изображения повреждён.") from exc
    if len(raw) > 8 * 1024 * 1024:
        raise HTTPException(413, "Фотография должна быть не больше 8 МБ.")
    try:
        analysis = analyze_product_photo(payload.image_data_url)
        return {"analysis": analysis, "analysis_signature": sign_analysis(analysis), "source": "single_photo", "facts_require_confirmation": True}
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    except (ValueError, httpx.HTTPError) as exc:
        raise HTTPException(502, "AI не смог надёжно проанализировать фотографию. Попробуйте другой снимок.") from exc


@router.post("/generate-draft")
def generate_draft(payload: BeginnerDraftRequest, user: User = Depends(get_current_user)):
    _verify_analysis(payload.analysis, payload.analysis_signature)
    fact_set = build_beginner_fact_set(payload.analysis, payload.confirmed_facts)
    try:
        draft = generate_grounded_copy(fact_set)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    except (ValueError, httpx.HTTPError) as exc:
        raise HTTPException(502, "AI-черновик не прошёл проверку подтверждённых фактов.") from exc
    return {
        "draft": draft,
        "fact_set_sha256": fact_set["sha256"],
        "source": "seller_confirmed_facts",
        "publish_requires_confirmation": True,
        "next_step": "unit_economics",
    }


@router.post("/calculate-economics")
def calculate_economics(payload: BeginnerEconomicsRequest, user: User = Depends(get_current_user)):
    return calculate_beginner_economics(payload)


@router.get("/projects")
def list_projects(store_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    store = resolve_store(db, user, store_id)
    projects = list(db.scalars(
        select(BeginnerProject)
        .where(BeginnerProject.store_id == store.id)
        .order_by(BeginnerProject.updated_at.desc())
        .limit(30)
    ).all())
    return {"store_id": store.id, "projects": [serialize_project(project) for project in projects]}


@router.post("/projects", status_code=201)
def create_project(payload: BeginnerProjectCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    store = resolve_store(db, user, payload.store_id)
    project = BeginnerProject(
        store_id=store.id,
        created_by_user_id=user.id,
        title=payload.title.strip(),
        stage=payload.stage,
        state=payload.state,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return serialize_project(project)


@router.patch("/projects/{project_id}")
def update_project(project_id: str, payload: BeginnerProjectPatch, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = accessible_project(db, user, project_id)
    if payload.title is not None:
        project.title = payload.title.strip()
    if payload.stage is not None:
        project.stage = payload.stage
    if payload.state is not None:
        project.state = payload.state
    db.commit()
    db.refresh(project)
    return serialize_project(project)
