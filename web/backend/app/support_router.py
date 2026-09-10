from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .data_health import store_data_health
from .db import get_db
from .models import AutomationControl, IncidentEvidenceBundle, OperationalAuditEvent, SupportTicket, User
from .security import get_current_user
from .store_access import require_store_admin, resolve_store
from .support_service import classify_support_message, evidence_hash, request_hash, sanitize_support_description

router = APIRouter(prefix="/support", tags=["support"])


class IncidentRequest(BaseModel):
    store_id: str = Field(min_length=1, max_length=36)
    description: str = Field(min_length=3, max_length=4000)
    correlation_id: str = Field(default="", max_length=120)
    category: Literal["auto", "incident", "security", "legal_or_billing"] = "auto"


def _public_ticket(row: SupportTicket, bundle: IncidentEvidenceBundle | None = None, *, can_stop: bool = False) -> dict:
    return {"id": row.id, "store_id": row.store_id, "category": row.category, "severity": row.severity,
            "forced_escalation_reason": row.forced_escalation_reason or None, "status": row.status,
            "description": row.sanitized_description, "correlation_id": row.correlation_id or None,
            "created_at": row.created_at, "updated_at": row.updated_at,
            "evidence": {"id": bundle.id, "sha256": bundle.bundle_sha256, "created_at": bundle.created_at} if bundle else None,
            "emergency_stop": {"available": can_stop, "href": "/director", "separate_confirmation_required": True}}


def _evidence(db: Session, store, ticket: SupportTicket) -> dict:
    health = store_data_health(db, store.id)
    control = db.scalar(select(AutomationControl).where(AutomationControl.store_id == store.id, AutomationControl.marketplace == "wildberries"))
    events = db.scalars(select(OperationalAuditEvent).where(OperationalAuditEvent.store_id == store.id)
                        .order_by(OperationalAuditEvent.created_at.desc()).limit(12)).all()
    # Deliberately keep audit payloads, request bodies, token hints and finance rows out.
    return {"schema_version": 1, "ticket_id": ticket.id, "store_id": store.id, "workspace_id": store.workspace_id,
            "marketplace": "wildberries", "captured_at": datetime.now(timezone.utc).isoformat(),
            "data_health": {"overall_status": health["overall_status"], "connected": health["connected"],
                            "sources": [{"key": item["key"], "status": item["status"], "age_seconds": item["age_seconds"]} for item in health["sources"]]},
            "automation_control": {"stopped": bool(control and control.stopped), "changed_at": control.changed_at.isoformat() if control and control.changed_at else None},
            "audit_index": [{"id": item.id, "event_type": item.event_type, "entity_type": item.entity_type,
                             "entity_id": item.entity_id, "created_at": item.created_at.isoformat() if item.created_at else None} for item in events],
            "redaction": "No credentials, personal buyer data, raw financial rows or audit payloads included."}


def _can_emergency_stop(db: Session, user: User, store) -> bool:
    try:
        require_store_admin(db, user, store)
        return True
    except HTTPException:
        return False


@router.post("/incidents", status_code=201)
def create_incident(payload: IncidentRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    store = resolve_store(db, user, payload.store_id)
    description = sanitize_support_description(payload.description)
    classification = classify_support_message(description)
    if payload.category != "auto":
        # A caller may elevate, never downgrade a deterministic forced category.
        if classification["forced_escalation_reason"]:
            pass
        elif payload.category in {"security", "legal_or_billing"}:
            classification = {"category": payload.category, "severity": "high", "forced_escalation_reason": payload.category, "human_review_required": True}
        else:
            classification = {"category": "incident", "severity": "medium", "forced_escalation_reason": "", "human_review_required": True}
    if not classification["human_review_required"]:
        raise HTTPException(422, "Это не похоже на инцидент. Для продуктовых вопросов база знаний будет добавлена отдельно; сейчас тикет создаётся только при риске или сбое.")
    correlation_id = payload.correlation_id.strip()
    digest = request_hash(category=classification["category"], description=description, correlation_id=correlation_id)
    existing = db.scalar(select(SupportTicket).where(SupportTicket.store_id == store.id, SupportTicket.created_by_user_id == user.id,
                                                      SupportTicket.request_sha256 == digest))
    if existing is not None:
        bundle = db.scalar(select(IncidentEvidenceBundle).where(IncidentEvidenceBundle.ticket_id == existing.id))
        return _public_ticket(existing, bundle, can_stop=_can_emergency_stop(db, user, store)) | {"message": "Такой инцидент уже зарегистрирован; повторный тикет не создан."}
    ticket = SupportTicket(workspace_id=store.workspace_id, store_id=store.id, created_by_user_id=user.id,
                           category=classification["category"], severity=classification["severity"],
                           forced_escalation_reason=classification["forced_escalation_reason"], status="open",
                           sanitized_description=description, correlation_id=correlation_id, request_sha256=digest)
    db.add(ticket)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(SupportTicket).where(SupportTicket.store_id == store.id, SupportTicket.created_by_user_id == user.id,
                                                          SupportTicket.request_sha256 == digest))
        if existing is None:
            raise
        bundle = db.scalar(select(IncidentEvidenceBundle).where(IncidentEvidenceBundle.ticket_id == existing.id))
        return _public_ticket(existing, bundle) | {"message": "Такой инцидент уже зарегистрирован; повторный тикет не создан."}
    evidence = _evidence(db, store, ticket)
    bundle = IncidentEvidenceBundle(ticket_id=ticket.id, workspace_id=store.workspace_id, store_id=store.id,
                                    bundle_sha256=evidence_hash(evidence), payload=evidence)
    db.add(bundle)
    db.add(OperationalAuditEvent(workspace_id=store.workspace_id, store_id=store.id, user_id=user.id,
                                 event_type="support.incident.created", entity_type="support_ticket", entity_id=ticket.id,
                                 payload={"category": ticket.category, "severity": ticket.severity, "forced_reason": ticket.forced_escalation_reason,
                                          "request_sha256": digest, "evidence_sha256": bundle.bundle_sha256}))
    db.commit(); db.refresh(ticket); db.refresh(bundle)
    return _public_ticket(ticket, bundle, can_stop=_can_emergency_stop(db, user, store)) | {"message": "Инцидент зарегистрирован и передан в защищённую очередь. Срок ответа не обещается, пока операционная политика не настроена."}


@router.get("/incidents")
def incidents(store_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    store = resolve_store(db, user, store_id)
    can_stop = _can_emergency_stop(db, user, store)
    query = select(SupportTicket).where(SupportTicket.store_id == store.id)
    if not can_stop:
        # Operators can follow their report, but cannot read a colleague's
        # incident description or correlate it with internal evidence.
        query = query.where(SupportTicket.created_by_user_id == user.id)
    rows = db.scalars(query.order_by(SupportTicket.created_at.desc()).limit(50)).all()
    bundles = {row.ticket_id: row for row in db.scalars(select(IncidentEvidenceBundle).where(IncidentEvidenceBundle.store_id == store.id)).all()}
    return {"items": [_public_ticket(row, bundles.get(row.id), can_stop=can_stop) for row in rows],
            "support_mode": "incident_intake_only", "knowledge_base_enabled": False, "automatic_actions": False}
