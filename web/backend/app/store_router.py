from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_db
from .models import Membership, MembershipRole, Store, User
from .security import get_current_user
from .store_access import list_accessible_stores

router = APIRouter()


class StoreCreateBody(BaseModel):
    workspace_id: str
    name: str = Field(min_length=2, max_length=160)
    client_name: str = Field(default='', max_length=160)


@router.get('/stores')
def stores(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = list_accessible_stores(db, user)
    return {
        'stores': [
            {
                'id': row.id,
                'workspace_id': row.workspace_id,
                'name': row.name,
                'client_name': row.client_name,
                'active': row.is_active,
            }
            for row in rows
        ]
    }


@router.post('/stores', status_code=status.HTTP_201_CREATED)
def create_store(body: StoreCreateBody, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    membership = db.scalar(select(Membership).where(
        Membership.user_id == user.id,
        Membership.workspace_id == body.workspace_id,
    ))
    if membership is None:
        raise HTTPException(404, 'Рабочее пространство не найдено.')
    if membership.role not in {MembershipRole.owner, MembershipRole.admin}:
        raise HTTPException(403, 'Недостаточно прав для создания магазина.')
    name = body.name.strip()
    exists = db.scalar(select(Store.id).where(Store.workspace_id == body.workspace_id, Store.name == name))
    if exists:
        raise HTTPException(409, 'Магазин с таким названием уже существует.')
    row = Store(workspace_id=body.workspace_id, name=name, client_name=body.client_name.strip())
    db.add(row)
    db.commit()
    db.refresh(row)
    return {'id': row.id, 'workspace_id': row.workspace_id, 'name': row.name, 'client_name': row.client_name, 'active': row.is_active}
