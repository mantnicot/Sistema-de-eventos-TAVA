from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import delete, func, select
from pydantic import BaseModel

from tava.domain.enums import UserRole
from tava.infrastructure.persistence.database import get_db
from tava.infrastructure.persistence.event_staff import (
    get_user_event_access,
    map_user_event_access,
    set_user_event_access,
)
from tava.infrastructure.persistence.models import (
    EmailVerificationTokenModel,
    EventModel,
    RefreshTokenModel,
    TicketModel,
    UserModel,
)
from tava.infrastructure.persistence.repositories.sqlalchemy_user_repository import SQLAlchemyUserRepository
from tava.presentation.api.dependencies import require_roles
from tava.presentation.api.http_errors import raise_user_error
from tava.presentation.api.schemas import UserAdminResponse, UserPermissionsUpdateRequest

router = APIRouter(prefix="/users", tags=["Usuarios (Admin)"])


class UserRoleUpdateRequest(BaseModel):
    role: UserRole


class UserStatusUpdateRequest(BaseModel):
    is_active: bool


def _to_admin_response(user, access: dict | None = None) -> UserAdminResponse:
    access = access or {}
    return UserAdminResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        phone=user.phone,
        email_verified=user.email_verified,
        is_active=user.is_active,
        validator_event_ids=list(access.get("validator_event_ids") or []),
        seller_event_ids=list(access.get("seller_event_ids") or []),
    )


async def _count_admins(db) -> int:
    result = await db.execute(
        select(func.count()).select_from(UserModel).where(UserModel.role == UserRole.ADMIN)
    )
    return int(result.scalar_one() or 0)


async def _validated_event_ids(db, event_ids: list[UUID]) -> list[UUID]:
    unique_ids = list(dict.fromkeys(event_ids))
    if not unique_ids:
        return []
    result = await db.execute(select(EventModel.id).where(EventModel.id.in_(unique_ids)))
    found = set(result.scalars().all())
    missing = [str(event_id) for event_id in unique_ids if event_id not in found]
    if missing:
        raise_user_error(400, "EVENT_NOT_FOUND", "Algunas obras no existen o fueron eliminadas")
    return unique_ids


async def _apply_role_event_access(db, user_id: UUID, role: UserRole, event_ids: list[UUID]) -> dict:
    if role in (UserRole.ADMIN, UserRole.GENERAL):
        await set_user_event_access(db, user_id, seller_event_ids=[], validator_event_ids=[])
        return await get_user_event_access(db, user_id)

    valid_ids = await _validated_event_ids(db, event_ids)
    seller_ids = valid_ids if role == UserRole.SELLER else []
    validator_ids = valid_ids if role == UserRole.VALIDATOR else []
    await set_user_event_access(
        db,
        user_id,
        seller_event_ids=seller_ids,
        validator_event_ids=validator_ids,
    )
    return await get_user_event_access(db, user_id)


@router.get("", response_model=list[UserAdminResponse])
async def list_users(
    role: UserRole | None = None,
    search: str | None = None,
    limit: int = Query(200, le=500),
    offset: int = 0,
    _user=Depends(require_roles(UserRole.ADMIN)),
    db=Depends(get_db),
):
    repo = SQLAlchemyUserRepository(db)
    users = await repo.list_by_role(role=role, limit=limit, offset=offset)
    if search:
        q = search.lower()
        users = [u for u in users if q in u.email.lower() or q in u.full_name.lower()]
    access_map = await map_user_event_access(db)
    return [_to_admin_response(u, access_map.get(u.id)) for u in users]


@router.patch("/{user_id}/permissions", response_model=UserAdminResponse)
async def set_user_permissions(
    user_id: UUID,
    body: UserPermissionsUpdateRequest,
    admin=Depends(require_roles(UserRole.ADMIN)),
    db=Depends(get_db),
):
    if admin.id == user_id and body.role != UserRole.ADMIN:
        raise_user_error(400, "CANNOT_DEMOTE_SELF", "No puedes quitarte el rol de administrador")

    repo = SQLAlchemyUserRepository(db)
    current = await repo.get_by_id(user_id)
    if not current:
        raise_user_error(404, "USER_NOT_FOUND", "Usuario no encontrado")

    if current.role == UserRole.ADMIN and body.role != UserRole.ADMIN:
        if await _count_admins(db) <= 1:
            raise_user_error(400, "LAST_ADMIN", "Debe quedar al menos un administrador")

    updated = await repo.update_user(
        user_id,
        role=body.role,
        is_active=body.is_active,
    )
    if not updated:
        raise_user_error(404, "USER_NOT_FOUND", "Usuario no encontrado")

    access = await _apply_role_event_access(db, user_id, body.role, body.event_ids)
    return _to_admin_response(updated, access)


@router.patch("/{user_id}/role", response_model=UserAdminResponse)
async def set_user_role(
    user_id: UUID,
    body: UserRoleUpdateRequest,
    admin=Depends(require_roles(UserRole.ADMIN)),
    db=Depends(get_db),
):
    if admin.id == user_id and body.role != UserRole.ADMIN:
        raise_user_error(400, "CANNOT_DEMOTE_SELF", "No puedes quitarte el rol de administrador")
    repo = SQLAlchemyUserRepository(db)
    current = await repo.get_by_id(user_id)
    if not current:
        raise_user_error(404, "USER_NOT_FOUND", "Usuario no encontrado")
    if current.role == UserRole.ADMIN and body.role != UserRole.ADMIN:
        if await _count_admins(db) <= 1:
            raise_user_error(400, "LAST_ADMIN", "Debe quedar al menos un administrador")
    updated = await repo.update_user(user_id, role=body.role)
    if not updated:
        raise_user_error(404, "USER_NOT_FOUND", "Usuario no encontrado")
    current_access = await get_user_event_access(db, user_id)
    keep_ids = (
        current_access["seller_event_ids"]
        if body.role == UserRole.SELLER
        else current_access["validator_event_ids"]
        if body.role == UserRole.VALIDATOR
        else []
    )
    access = await _apply_role_event_access(db, user_id, body.role, keep_ids)
    return _to_admin_response(updated, access)


@router.patch("/{user_id}/status", response_model=UserAdminResponse)
async def set_user_status(
    user_id: UUID,
    body: UserStatusUpdateRequest,
    admin=Depends(require_roles(UserRole.ADMIN)),
    db=Depends(get_db),
):
    if admin.id == user_id and not body.is_active:
        raise_user_error(400, "CANNOT_DEACTIVATE_SELF", "No puedes desactivar tu propia cuenta")
    repo = SQLAlchemyUserRepository(db)
    updated = await repo.update_user(user_id, is_active=body.is_active)
    if not updated:
        raise_user_error(404, "USER_NOT_FOUND", "Usuario no encontrado")
    access = await get_user_event_access(db, user_id)
    return _to_admin_response(updated, access)


@router.delete("/{user_id}")
async def delete_user(
    user_id: UUID,
    admin=Depends(require_roles(UserRole.ADMIN)),
    db=Depends(get_db),
):
    if admin.id == user_id:
        raise_user_error(400, "CANNOT_DELETE_SELF", "No puedes eliminar tu propia cuenta admin")
    result = await db.execute(select(UserModel).where(UserModel.id == user_id))
    target = result.scalar_one_or_none()
    if not target:
        raise_user_error(404, "USER_NOT_FOUND", "Usuario no encontrado")
    if target.role == UserRole.ADMIN:
        raise_user_error(400, "CANNOT_DELETE_ADMIN", "No se puede eliminar un administrador")
    tickets = await db.execute(select(TicketModel.id).where(TicketModel.owner_id == user_id).limit(1))
    if tickets.scalar_one_or_none():
        raise_user_error(
            400,
            "USER_HAS_TICKETS",
            "Este usuario tiene boletas. Desactívalo en lugar de borrarlo.",
        )
    await db.execute(delete(EmailVerificationTokenModel).where(EmailVerificationTokenModel.user_id == user_id))
    await db.execute(delete(RefreshTokenModel).where(RefreshTokenModel.user_id == user_id))
    await db.delete(target)
    await db.flush()
    return {"message": "Usuario eliminado", "success": True}
