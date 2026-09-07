import asyncio
import logging

import httpx
from sqlalchemy.orm import Session

from .config import get_settings
from .db import SessionLocal
from .fbo_service import fetch_wb_slots
from .fbo_worker import process_watch
from .marketplace_connections import decrypt_connection
from .models import FboWatch, MarketplaceConnection

logger = logging.getLogger(__name__)


def _load_connection(db: Session, user_id: str) -> MarketplaceConnection | None:
    return (
        db.query(MarketplaceConnection)
        .filter(
            MarketplaceConnection.user_id == user_id,
            MarketplaceConnection.marketplace == "wildberries",
            MarketplaceConnection.enabled.is_(True),
        )
        .first()
    )


async def process_enabled_watches_once() -> dict[str, int]:
    """Process each seller account at most once per cycle, then fan out to its watches."""
    db = SessionLocal()
    checked_accounts = 0
    checked_watches = 0
    pushes_sent = 0
    try:
        watches = (
            db.query(FboWatch)
            .filter(
                FboWatch.enabled.is_(True),
                FboWatch.marketplace == "wildberries",
            )
            .all()
        )
        by_user: dict[str, list[FboWatch]] = {}
        for watch in watches:
            by_user.setdefault(watch.user_id, []).append(watch)

        for user_id, user_watches in by_user.items():
            connection = _load_connection(db, user_id)
            if not connection:
                continue
            try:
                token = decrypt_connection(connection)
                slots = await fetch_wb_slots(token)
                checked_accounts += 1
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code if exc.response is not None else None
                logger.warning("WB slot monitor request failed for user=%s status=%s", user_id, status)
                continue
            except Exception:
                logger.exception("WB slot monitor failed for user=%s", user_id)
                continue

            for watch in user_watches:
                checked_watches += 1
                pushes_sent += process_watch(db, watch, slots)
    finally:
        db.close()

    return {
        "checked_accounts": checked_accounts,
        "checked_watches": checked_watches,
        "pushes_sent": pushes_sent,
    }


async def monitor_forever(stop_event: asyncio.Event) -> None:
    settings = get_settings()
    interval = max(10, settings.fbo_poll_seconds)
    while not stop_event.is_set():
        try:
            await process_enabled_watches_once()
        except Exception:
            logger.exception("FBO monitor cycle failed")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
        except asyncio.TimeoutError:
            pass
