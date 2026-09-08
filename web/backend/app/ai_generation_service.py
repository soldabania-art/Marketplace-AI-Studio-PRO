import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from .config import get_settings
from .models import AIGeneration, GenerationStatus, Store, User


def stable_hash(payload: dict) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def begin_generation(db: Session, *, store: Store, user: User, feature: str, subject_id: str, input_payload: dict, fact_set_sha256: str = "") -> AIGeneration:
    generation = AIGeneration(
        workspace_id=store.workspace_id,
        store_id=store.id,
        user_id=user.id,
        feature=feature,
        subject_id=str(subject_id),
        input_hash=stable_hash(input_payload),
        fact_set_sha256=fact_set_sha256,
        model=get_settings().openai_model,
        input_payload=input_payload,
        status=GenerationStatus.pending,
    )
    db.add(generation)
    db.commit()
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
