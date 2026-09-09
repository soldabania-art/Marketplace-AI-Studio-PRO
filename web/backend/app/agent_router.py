from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .agent_network import learning_payload_hash, public_network, registry_checksum, require_capability, route_goal, sanitize_learning_note
from .db import get_db
from .models import AgentLearningRecord, AgentWorkOrder, AutomationControl, OperationalAuditEvent, User
from .security import get_current_user, require_platform_admin
from .store_access import require_store_admin, resolve_store

router = APIRouter(prefix="/agents", tags=["agents"])
admin_router = APIRouter(prefix="/admin/agents", tags=["admin-agents"])


class LearningCandidateRequest(BaseModel):
    store_id: str = Field(min_length=1, max_length=36)
    agent_key: str = Field(min_length=1, max_length=40)
    signal: Literal["helpful", "not_helpful", "incorrect", "unsafe"]
    source_type: Literal["director_action", "ai_generation", "support_answer", "manual"] = "manual"
    source_id: str = Field(default="", max_length=160)
    note: str = Field(default="", max_length=4000)


class LearningReviewRequest(BaseModel):
    decision: Literal["approved", "rejected"]
    note: str = Field(default="", max_length=1000)


class WorkOrderRequest(BaseModel):
    store_id: str = Field(min_length=1, max_length=36)
    goal_type: Literal["profit_review", "content_improvement", "stock_risk", "source_health", "support"]
    subject_id: str = Field(default="", max_length=160)
    instruction: str = Field(min_length=3, max_length=2000)


def _public_learning(row: AgentLearningRecord) -> dict:
    return {
        "id": row.id,
        "store_id": row.store_id,
        "agent_key": row.agent_key,
        "signal": row.signal,
        "source_type": row.source_type,
        "source_id": row.source_id,
        "note": row.sanitized_note,
        "status": row.status,
        "created_at": row.created_at,
        "reviewed_at": row.reviewed_at,
        "promotion_applied": False,
    }


def _public_work_order(row: AgentWorkOrder) -> dict:
    return {
        "id": row.id,
        "store_id": row.store_id,
        "goal_type": row.goal_type,
        "assigned_agent_key": row.assigned_agent_key,
        "capability": row.capability,
        "subject_id": row.subject_id,
        "instruction": row.sanitized_instruction,
        "status": row.status,
        "policy_version": row.policy_version,
        "policy_sha256": row.policy_sha256,
        "external_write": row.external_write,
        "created_at": row.created_at,
    }


@router.get("/network")
def network(store_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    store = resolve_store(db, user, store_id)
    control = db.scalar(select(AutomationControl).where(AutomationControl.store_id == store.id, AutomationControl.marketplace == "wildberries"))
    return public_network() | {
        "store_id": store.id,
        "workspace_id": store.workspace_id,
        "control": {
            "stopped": bool(control and control.stopped),
            "owner_approval_required_for_external_writes": True,
            "platform_policy_can_override_security_denial": False,
        },
    }


@router.post("/work-orders", status_code=201)
def create_work_order(payload: WorkOrderRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    store = resolve_store(db, user, payload.store_id)
    require_store_admin(db, user, store)
    route = route_goal(payload.goal_type)
    instruction = sanitize_learning_note(payload.instruction)
    subject_id = payload.subject_id.strip()
    request_sha256 = learning_payload_hash(agent_key=route["agent_key"], signal=payload.goal_type,
                                           source_type="work_order", source_id=subject_id, note=instruction)
    existing = db.scalar(select(AgentWorkOrder).where(
        AgentWorkOrder.store_id == store.id,
        AgentWorkOrder.requested_by_user_id == user.id,
        AgentWorkOrder.request_sha256 == request_sha256,
    ))
    if existing is not None:
        return _public_work_order(existing) | {"message": "Такая задача уже поставлена; повтор не создавался."}
    row = AgentWorkOrder(
        workspace_id=store.workspace_id,
        store_id=store.id,
        requested_by_user_id=user.id,
        goal_type=payload.goal_type,
        assigned_agent_key=route["agent_key"],
        capability=route["capability"],
        subject_id=subject_id,
        sanitized_instruction=instruction,
        request_sha256=request_sha256,
        status="planned",
        policy_version=public_network()["version"],
        policy_sha256=registry_checksum(),
        external_write=False,
    )
    db.add(row)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(AgentWorkOrder).where(
            AgentWorkOrder.store_id == payload.store_id,
            AgentWorkOrder.requested_by_user_id == user.id,
            AgentWorkOrder.request_sha256 == request_sha256,
        ))
        if existing is None:
            raise
        return _public_work_order(existing) | {"message": "Такая задача уже поставлена; повтор не создавался."}
    db.add(OperationalAuditEvent(
        workspace_id=store.workspace_id,
        store_id=store.id,
        user_id=user.id,
        event_type="agent.work_order.planned",
        entity_type="agent_work_order",
        entity_id=row.id,
        payload={"goal_type": row.goal_type, "agent_key": row.assigned_agent_key, "capability": row.capability,
                 "request_sha256": row.request_sha256, "policy_sha256": row.policy_sha256, "external_write": False},
    ))
    db.commit()
    db.refresh(row)
    return _public_work_order(row) | {"message": "AI Director принял задачу и безопасно назначил ответственного агента."}


@router.get("/work-orders")
def work_orders(store_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    store = resolve_store(db, user, store_id)
    rows = db.scalars(select(AgentWorkOrder).where(AgentWorkOrder.store_id == store.id)
                      .order_by(AgentWorkOrder.created_at.desc()).limit(100)).all()
    return {"items": [_public_work_order(row) for row in rows], "execution_enabled": False}


@router.post("/learning", status_code=201)
def create_learning_candidate(payload: LearningCandidateRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    store = resolve_store(db, user, payload.store_id)
    require_capability(payload.agent_key, "recommend.read" if payload.agent_key == "director" else {
        "finance": "profit.explain", "content": "copy.draft", "supply": "supply_plan.draft",
        "data_health": "source_health.read", "support": "knowledge.read", "security": "audit.verify",
    }.get(payload.agent_key, ""))
    note = sanitize_learning_note(payload.note)
    payload_sha256 = learning_payload_hash(agent_key=payload.agent_key, signal=payload.signal, source_type=payload.source_type,
                                           source_id=payload.source_id.strip(), note=note)
    existing = db.scalar(select(AgentLearningRecord).where(
        AgentLearningRecord.store_id == store.id,
        AgentLearningRecord.user_id == user.id,
        AgentLearningRecord.payload_sha256 == payload_sha256,
    ))
    if existing is not None:
        return _public_learning(existing) | {"message": "Этот кандидат уже сохранён; повтор не создавался."}
    row = AgentLearningRecord(
        workspace_id=store.workspace_id,
        store_id=store.id,
        user_id=user.id,
        agent_key=payload.agent_key,
        signal=payload.signal,
        source_type=payload.source_type,
        source_id=payload.source_id.strip(),
        payload_sha256=payload_sha256,
        sanitized_note=note,
        status="candidate",
    )
    db.add(row)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(AgentLearningRecord).where(
            AgentLearningRecord.store_id == store.id,
            AgentLearningRecord.user_id == user.id,
            AgentLearningRecord.payload_sha256 == payload_sha256,
        ))
        if existing is None:
            raise
        return _public_learning(existing) | {"message": "Этот кандидат уже сохранён; повтор не создавался."}
    db.add(OperationalAuditEvent(
        workspace_id=store.workspace_id,
        store_id=store.id,
        user_id=user.id,
        event_type="agent.learning.candidate_created",
        entity_type="agent_learning",
        entity_id=row.id,
        payload={"agent_key": row.agent_key, "signal": row.signal, "source_type": row.source_type, "payload_sha256": row.payload_sha256},
    ))
    db.commit()
    db.refresh(row)
    return _public_learning(row) | {"message": "Отзыв сохранён как кандидат. Он не изменил агента и ожидает проверки."}


@router.get("/learning")
def learning_candidates(store_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    store = resolve_store(db, user, store_id)
    require_store_admin(db, user, store)
    rows = db.scalars(select(AgentLearningRecord).where(AgentLearningRecord.store_id == store.id).order_by(AgentLearningRecord.created_at.desc()).limit(100)).all()
    return {"items": [_public_learning(row) for row in rows], "auto_training": False}


@admin_router.get("/learning")
def admin_learning(status: Literal["candidate", "approved", "rejected"] = Query(default="candidate"),
                   _: User = Depends(require_platform_admin), db: Session = Depends(get_db)):
    rows = db.scalars(select(AgentLearningRecord).where(AgentLearningRecord.status == status).order_by(AgentLearningRecord.created_at.asc()).limit(200)).all()
    return {"items": [_public_learning(row) for row in rows], "promotion_requires_evaluation": True}


@admin_router.patch("/learning/{record_id}")
def review_learning(record_id: str, payload: LearningReviewRequest, admin: User = Depends(require_platform_admin), db: Session = Depends(get_db)):
    row = db.query(AgentLearningRecord).filter(AgentLearningRecord.id == record_id).with_for_update().first()
    if row is None:
        raise HTTPException(404, "Кандидат обучения не найден.")
    if row.status != "candidate":
        raise HTTPException(409, "Решение по этому кандидату уже принято.")
    row.status = payload.decision
    row.reviewed_by_user_id = admin.id
    row.review_note = sanitize_learning_note(payload.note)
    row.reviewed_at = datetime.now(timezone.utc)
    db.add(OperationalAuditEvent(
        workspace_id=row.workspace_id,
        store_id=row.store_id,
        user_id=admin.id,
        event_type=f"agent.learning.{payload.decision}",
        entity_type="agent_learning",
        entity_id=row.id,
        payload={"agent_key": row.agent_key, "payload_sha256": row.payload_sha256, "promotion_applied": False},
    ))
    db.commit()
    db.refresh(row)
    return _public_learning(row) | {
        "message": "Решение записано. Изменения агента потребуют отдельной оценки и новой версии политики.",
        "promotion_requires_evaluation": True,
    }
