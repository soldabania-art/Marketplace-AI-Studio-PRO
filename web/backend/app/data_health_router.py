from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .data_health import store_data_health
from .db import get_db
from .models import User
from .security import get_current_user
from .store_access import resolve_store

router = APIRouter(prefix="/data-health", tags=["data-health"])


@router.get("")
def health(store_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    store = resolve_store(db, user, store_id)
    return {"store_id": store.id, "store_name": store.name, **store_data_health(db, store.id)}
