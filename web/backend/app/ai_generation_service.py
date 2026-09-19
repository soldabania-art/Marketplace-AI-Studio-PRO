import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .config import get_settings
from .models import AIGeneration, GenerationStatus, Store, User


class GenerationAdmissionConflict(Exception):
    """An identical paid generation is already pending for this store."""


_ADMISSION_INDEX = "uq_ai_generation_pending_admission"
_SQLITE_ADMISSION_CONSTRAINT = (
    "UNIQUE constraint failed: ai_generations.store_id, ai_generations.feature, "
    "ai_generations.subject_type, ai_generations.subject_id, ai_generations.input_hash, "
    "ai_generations.fact_set_sha256, ai_generations.model"
)


def _is_pending_admission_conflict(error: IntegrityError) -> bool:
    diagnostic = getattr(error.orig, "diag", None)
    if getattr(diagnostic, "constraint_name", None) == _ADMISSION_INDEX:
        return True
    return str(error.orig).strip() == _SQLITE_ADMISSION_CONSTRAINT


def stable_hash(payload: dict) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def begin_generation(db: Session, *, store: Store, user: User, feature: str, subject_id: str, input_payload: dict, fact_set_sha256: str = "", model: str | None = None) -> AIGeneration:
    resolved_model = model or get_settings().openai_model
    input_hash = stable_hash(input_payload)
    pending = db.query(AIGeneration).filter(
        AIGeneration.store_id == store.id,
        AIGeneration.feature == feature,
        AIGeneration.subject_type == "product",
        AIGeneration.subject_id == str(subject_id),
        AIGeneration.input_hash == input_hash,
        AIGeneration.fact_set_sha256 == fact_set_sha256,
        AIGeneration.model == resolved_model,
        AIGeneration.status == GenerationStatus.pending,
    ).first()
    if pending:
        raise GenerationAdmissionConflict()
    generation = AIGeneration(
        workspace_id=store.workspace_id,
        store_id=store.id,
        user_id=user.id,
        feature=feature,
        subject_id=str(subject_id),
        input_hash=input_hash,
        fact_set_sha256=fact_set_sha256,
        model=resolved_model,
        input_payload=input_payload,
        status=GenerationStatus.pending,
    )
    db.add(generation)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if _is_pending_admission_conflict(exc):
            raise GenerationAdmissionConflict() from exc
        raise
    db.refresh(generation)
    return generation


def complete_generation(db: Session, generation: AIGeneration, result: dict, metadata: dict | None = None) -> None:
    metadata = metadata or {}
    generation.result_payload = result
    generation.model = metadata.get("model") or generation.model
    generation.token_usage = metadata.get("usage") or {}
    generation.estimated_cost_microusd = int(metadata.get("estimated_cost_microusd") or 0)
    generation.provider_response_id = metadata.get("response_id") or ""
    generation.status = GenerationStatus.completed
    generation.completed_at = datetime.now(timezone.utc)
    db.commit()


def fail_generation(db: Session, generation: AIGeneration, error: Exception) -> None:
    generation.status = GenerationStatus.failed
    generation.error = str(error)[:2000]
    generation.completed_at = datetime.now(timezone.utc)
    db.commit()


def public_generation(generation: AIGeneration, include_result: bool = True) -> dict:
    payload = {
        "id": generation.id,
        "feature": generation.feature,
        "subject_type": generation.subject_type,
        "subject_id": generation.subject_id,
        "fact_set_sha256": generation.fact_set_sha256,
        "model": generation.model,
        "status": generation.status.value,
        "token_usage": generation.token_usage,
        "estimated_cost_microusd": generation.estimated_cost_microusd,
        "created_at": generation.created_at,
        "completed_at": generation.completed_at,
    }
    if include_result:
        payload["result"] = generation.result_payload
        payload["error"] = generation.error
    return payload
