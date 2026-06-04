from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from tava.domain.enums import UserRole
from tava.infrastructure.persistence.database import get_db
from tava.infrastructure.persistence.repositories.sqlalchemy_user_repository import SQLAlchemyUserRepository
from tava.presentation.api.dependencies import require_roles
from tava.presentation.api.http_errors import raise_user_error
from tava.presentation.api.schemas import UserAdminResponse

router = APIRouter(prefix="/users", tags=["Usuarios (Admin)"])


class UserRoleUpdateRequest(BaseModel):
    role: UserRole


class UserStatusUpdateRequest(BaseModel):
    is_active: bool


@router.get("", response_model=list[UserAdminResponse])
async def list_users(
    role: UserRole | None = None,
    search: str | None = None,
    limit: int = Query(50, le=100),
    offset: int = 0,
    _user=Depends(require_roles(UserRole.ADMIN)),
    db=Depends(get_db),
):
    repo = SQLAlchemyUserRepository(db)
    users = await repo.list_by_role(role=role, limit=limit, offset=offset)
    if search:
        q = search.lower()
        users = [u for u in users if q in u.email.lower() or q in u.full_name.lower()]
    return [
        UserAdminResponse(
            id=u.id,
            email=u.email,
            full_name=u.full_name,
            role=u.role,
            phone=u.phone,
            email_verified=u.email_verified,
            is_active=u.is_active,
        )
        for u in users
    ]


@router.patch("/{user_id}/role", response_model=UserAdminResponse)
async def set_user_role(
    user_id: UUID,
    body: UserRoleUpdateRequest,
    admin=Depends(require_roles(UserRole.ADMIN)),
    db=Depends(get_db),
):
    if body.role == UserRole.ADMIN and admin.role != UserRole.ADMIN:
        raise_user_error(403, "FORBIDDEN", "No puedes asignar rol administrador")
    repo = SQLAlchemyUserRepository(db)
    updated = await repo.update_user(user_id, role=body.role)
    if not updated:
        raise_user_error(404, "USER_NOT_FOUND", "Usuario no encontrado")
    return UserAdminResponse(
        id=updated.id,
        email=updated.email,
        full_name=updated.full_name,
        role=updated.role,
        phone=updated.phone,
        email_verified=updated.email_verified,
        is_active=updated.is_active,
    )


@router.patch("/{user_id}/status", response_model=UserAdminResponse)
async def set_user_status(
    user_id: UUID,
    body: UserStatusUpdateRequest,
    _user=Depends(require_roles(UserRole.ADMIN)),
    db=Depends(get_db),
):
    repo = SQLAlchemyUserRepository(db)
    updated = await repo.update_user(user_id, is_active=body.is_active)
    if not updated:
        raise_user_error(404, "USER_NOT_FOUND", "Usuario no encontrado")
    return UserAdminResponse(
        id=updated.id,
        email=updated.email,
        full_name=updated.full_name,
        role=updated.role,
        phone=updated.phone,
        email_verified=updated.email_verified,
        is_active=updated.is_active,
    )
