from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .db import get_db
from .billing_service import entitlement_snapshot, latest_subscription
from .models import MarketplaceConnection, Membership, MembershipRole, Store, User, Workspace
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
    store_ids = [row.id for row in rows]
    connections = db.scalars(select(MarketplaceConnection).where(MarketplaceConnection.store_id.in_(store_ids))).all() if store_ids else []
    connections_by_store = {}
    for connection in connections:
        connections_by_store.setdefault(connection.store_id, []).append({
            'code': connection.marketplace,
            'connected': True,
            'enabled': bool(connection.enabled),
        })
    memberships = db.scalars(
        select(Membership).where(Membership.user_id == user.id)
    ).all()
    workspace_ids = [m.workspace_id for m in memberships]
    workspace_map = {
        row.id: row for row in db.scalars(select(Workspace).where(Workspace.id.in_(workspace_ids))).all()
    } if workspace_ids else {}
    return {
        'stores': [
            {
                'id': row.id,
                'workspace_id': row.workspace_id,
                'name': row.name,
                'client_name': row.client_name,
                'active': row.is_active,
                'marketplaces': sorted(connections_by_store.get(row.id, []), key=lambda item: item['code']),
            }
            for row in rows
        ],
        'workspaces': [
            {
                'id': membership.workspace_id,
                'name': workspace_map[membership.workspace_id].name if membership.workspace_id in workspace_map else 'Workspace',
                'role': membership.role.value,
                'can_manage_stores': membership.role in {MembershipRole.owner, MembershipRole.admin},
            }
            for membership in memberships
        ],
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
    billing = entitlement_snapshot(latest_subscription(db, body.workspace_id))
    store_limit = int(billing['entitlements']['stores_limit'])
    current_stores = db.scalar(select(func.count(Store.id)).where(Store.workspace_id == body.workspace_id, Store.is_active.is_(True))) or 0
    if current_stores >= store_limit:
        raise HTTPException(402, f'Тариф {billing["plan"].upper()} позволяет подключить магазинов: {store_limit}.')
    name = body.name.strip()
    exists = db.scalar(select(Store.id).where(Store.workspace_id == body.workspace_id, Store.name == name))
    if exists:
        raise HTTPException(409, 'Магазин с таким названием уже существует.')
    row = Store(workspace_id=body.workspace_id, name=name, client_name=body.client_name.strip())
    db.add(row)
    db.commit()
    db.refresh(row)
    return {'id': row.id, 'workspace_id': row.workspace_id, 'name': row.name, 'client_name': row.client_name, 'active': row.is_active}
