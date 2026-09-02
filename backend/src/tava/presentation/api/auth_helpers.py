"""Helpers de permisos sin dependencias de FastAPI (evita imports circulares)."""
from uuid import UUID

from tava.domain.enums import UserRole


def is_platform_admin(user) -> bool:
    return bool(getattr(user, "is_platform_admin", False))


def can_manage_event(user, event) -> bool:
    if is_platform_admin(user):
        return True
    return user.role == UserRole.ORGANIZER and event.organizer_id == user.id
