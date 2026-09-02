"""Dependencias FastAPI para admin global y organizadores."""
from uuid import UUID

from fastapi import Depends, HTTPException, status

from tava.domain.enums import UserRole
from tava.infrastructure.persistence.models import EventModel, UserModel
from tava.presentation.api.auth_helpers import can_manage_event, is_platform_admin
from tava.presentation.api.dependencies import get_current_user


async def require_platform_admin(user=Depends(get_current_user)) -> UserModel:
    if not is_platform_admin(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo el administrador global")
    return user


async def require_event_manager(user=Depends(get_current_user)) -> UserModel:
    if is_platform_admin(user) or user.role == UserRole.ORGANIZER:
        return user
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin permisos para gestionar eventos")


async def require_event_access(event_id: UUID, user: UserModel, event: EventModel | None) -> EventModel:
    if not event:
        raise HTTPException(status_code=404, detail="Evento no encontrado")
    if not can_manage_event(user, event):
        raise HTTPException(status_code=403, detail="No puedes gestionar este evento")
    return event
