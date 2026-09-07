from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Membership, MembershipRole, Store, User, Workspace


def accessible_store_query(user_id: str):
    return (
        select(Store)
        .join(Membership, Membership.workspace_id == Store.workspace_id)
        .where(Membership.user_id == user_id, Store.is_active.is_(True))
        .order_by(Store.created_at.asc())
    )


def list_accessible_stores(db: Session, user: User) -> list[Store]:
    stores = list(db.scalars(accessible_store_query(user.id)).all())
    if stores:
        return stores

    memberships = list(db.scalars(select(Membership).where(Membership.user_id == user.id)).all())
    if len(memberships) == 1:
        workspace = db.get(Workspace, memberships[0].workspace_id)
        if workspace is not None:
            store = Store(workspace_id=workspace.id, name=workspace.name or 'Основной магазин')
            db.add(store)
            db.commit()
            db.refresh(store)
            return [store]
    return []


def resolve_store(db: Session, user: User, store_id: str | None = None) -> Store:
    if store_id:
        store = db.scalar(accessible_store_query(user.id).where(Store.id == store_id))
        if store is None:
            raise HTTPException(404, 'Магазин не найден или у вас нет к нему доступа.')
        return store

    stores = list_accessible_stores(db, user)
    if not stores:
        raise HTTPException(409, 'Сначала создайте магазин в рабочем пространстве.')
    if len(stores) > 1:
        raise HTTPException(409, 'Выберите магазин: для аккаунта доступно несколько магазинов.')
    return stores[0]


def require_store_admin(db: Session, user: User, store: Store) -> Membership:
    membership = db.scalar(
        select(Membership).where(
            Membership.user_id == user.id,
            Membership.workspace_id == store.workspace_id,
        )
    )
    if membership is None or membership.role not in {MembershipRole.owner, MembershipRole.admin}:
        raise HTTPException(403, 'Недостаточно прав для управления этим магазином.')
    return membership
