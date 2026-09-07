import base64
import binascii
import hashlib
import hmac
import json
import re

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .ai_card_factory import analyze_product_photo, generate_grounded_copy
from .config import get_settings
from .models import User
from .security import get_current_user

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
