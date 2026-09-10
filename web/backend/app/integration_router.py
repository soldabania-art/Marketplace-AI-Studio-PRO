from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_db
from .integration_catalog import public_catalog
from .models import MarketplaceConnection, User
from .security import get_current_user
from .store_access import resolve_store

router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.get("/catalog")
def integration_catalog(store_id: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    store = resolve_store(db, user, store_id)
    connected = db.scalars(select(MarketplaceConnection.marketplace).where(MarketplaceConnection.store_id == store.id, MarketplaceConnection.enabled.is_(True))).all()
    return {"store_id": store.id, "store_name": store.name, **public_catalog(connected)}
