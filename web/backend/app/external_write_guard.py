import hashlib

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from .models import AutomationControl, OperationalAuditEvent


def _scope_lock_key(*, workspace_id: str, store_id: str, marketplace: str) -> int:
    """Return a stable signed bigint for PostgreSQL transaction advisory locks."""
    scope = f"external-write:{workspace_id}:{store_id}:{marketplace}".encode()
    return int.from_bytes(hashlib.sha256(scope).digest()[:8], "big", signed=True)


def lock_external_write_scope(
    db: Session,
    *,
    workspace_id: str,
    store_id: str,
    marketplace: str,
) -> None:
    """Serialize STOP changes and dispatch admission, including a missing control row."""
    bind = db.get_bind()
    if bind.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": _scope_lock_key(
            workspace_id=workspace_id,
            store_id=store_id,
            marketplace=marketplace,
        )})


def require_external_write_allowed(
    db: Session,
    *,
    workspace_id: str,
    store_id: str,
    marketplace: str,
    user_id: str,
    operation: str,
    entity_type: str,
    entity_id: str,
    lock: bool = False,
) -> None:
    """Fail closed when the store/workspace STOP scope blocks a new provider write."""
    if lock:
        lock_external_write_scope(
            db,
            workspace_id=workspace_id,
            store_id=store_id,
            marketplace=marketplace,
        )
    db.expire_all()
    query = db.query(AutomationControl).filter(
        AutomationControl.workspace_id == workspace_id,
        AutomationControl.store_id == store_id,
        AutomationControl.marketplace == marketplace,
    )
    if lock:
        query = query.with_for_update()
    control = query.first()
    if control is None or not control.stopped:
        return

    scope = {
        "type": "store_marketplace",
        "workspace_id": workspace_id,
        "store_id": store_id,
        "marketplace": marketplace,
        "automation_control_id": control.id,
    }
    db.add(OperationalAuditEvent(
        workspace_id=workspace_id,
        store_id=store_id,
        user_id=user_id,
        event_type="external_write.refused",
        entity_type=entity_type,
        entity_id=entity_id,
        payload={
            "operation": operation,
            "reason": control.reason,
            "stopped": True,
            "stop_scope": scope,
            "provider_request_started": False,
        },
    ))
    db.commit()
    raise HTTPException(
        423,
        detail={
            "code": "EMERGENCY_STOP_ACTIVE",
            "message": "Emergency STOP включён: новая отправка в маркетплейс заблокирована.",
            "stop_scope": scope,
            "reason": control.reason,
        },
    )
