"""Asignación de validadores y vendedores por evento."""
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from tava.domain.enums import UserRole
from tava.infrastructure.persistence.models import EventStaffAssignmentModel


async def can_access_event(
    session: AsyncSession,
    user_id: UUID,
    user_role: UserRole,
    event_id: UUID,
    staff_role: str,
    *,
    is_platform_admin: bool = False,
) -> bool:
    if is_platform_admin:
        return True
    if staff_role == "validator" and user_role != UserRole.VALIDATOR:
        return False
    if staff_role == "seller" and user_role not in (UserRole.SELLER,):
        return False
    result = await session.execute(
        select(EventStaffAssignmentModel.id).where(
            EventStaffAssignmentModel.user_id == user_id,
            EventStaffAssignmentModel.event_id == event_id,
            EventStaffAssignmentModel.staff_role == staff_role,
        )
    )
    return result.scalar_one_or_none() is not None


async def list_assigned_event_ids(
    session: AsyncSession, user_id: UUID, staff_role: str
) -> list[UUID]:
    result = await session.execute(
        select(EventStaffAssignmentModel.event_id).where(
            EventStaffAssignmentModel.user_id == user_id,
            EventStaffAssignmentModel.staff_role == staff_role,
        )
    )
    return list(result.scalars().all())


async def get_event_staff(session: AsyncSession, event_id: UUID) -> dict:
    result = await session.execute(
        select(EventStaffAssignmentModel).where(EventStaffAssignmentModel.event_id == event_id)
    )
    rows = result.scalars().all()
    validators = [str(r.user_id) for r in rows if r.staff_role == "validator"]
    sellers = [str(r.user_id) for r in rows if r.staff_role == "seller"]
    return {"validator_ids": validators, "seller_ids": sellers}


async def set_event_staff(
    session: AsyncSession,
    event_id: UUID,
    validator_ids: list[UUID],
    seller_ids: list[UUID],
) -> None:
    await session.execute(
        delete(EventStaffAssignmentModel).where(EventStaffAssignmentModel.event_id == event_id)
    )
    for uid in validator_ids:
        session.add(
            EventStaffAssignmentModel(user_id=uid, event_id=event_id, staff_role="validator")
        )
    for uid in seller_ids:
        session.add(
            EventStaffAssignmentModel(user_id=uid, event_id=event_id, staff_role="seller")
        )
    await session.flush()


def _empty_user_access() -> dict[str, list[UUID]]:
    return {"validator_event_ids": [], "seller_event_ids": []}


async def map_user_event_access(session: AsyncSession) -> dict[UUID, dict[str, list[UUID]]]:
    result = await session.execute(select(EventStaffAssignmentModel))
    mapping: dict[UUID, dict[str, list[UUID]]] = {}
    for row in result.scalars().all():
        bucket = mapping.setdefault(row.user_id, _empty_user_access())
        if row.staff_role == "validator":
            bucket["validator_event_ids"].append(row.event_id)
        elif row.staff_role == "seller":
            bucket["seller_event_ids"].append(row.event_id)
    return mapping


async def get_user_event_access(session: AsyncSession, user_id: UUID) -> dict[str, list[UUID]]:
    result = await session.execute(
        select(EventStaffAssignmentModel).where(EventStaffAssignmentModel.user_id == user_id)
    )
    access = _empty_user_access()
    for row in result.scalars().all():
        if row.staff_role == "validator":
            access["validator_event_ids"].append(row.event_id)
        elif row.staff_role == "seller":
            access["seller_event_ids"].append(row.event_id)
    return access


async def set_user_event_access(
    session: AsyncSession,
    user_id: UUID,
    *,
    seller_event_ids: list[UUID],
    validator_event_ids: list[UUID],
) -> None:
    await session.execute(
        delete(EventStaffAssignmentModel).where(EventStaffAssignmentModel.user_id == user_id)
    )
    seen_seller: set[UUID] = set()
    seen_validator: set[UUID] = set()
    for event_id in seller_event_ids:
        if event_id in seen_seller:
            continue
        seen_seller.add(event_id)
        session.add(
            EventStaffAssignmentModel(user_id=user_id, event_id=event_id, staff_role="seller")
        )
    for event_id in validator_event_ids:
        if event_id in seen_validator:
            continue
        seen_validator.add(event_id)
        session.add(
            EventStaffAssignmentModel(user_id=user_id, event_id=event_id, staff_role="validator")
        )
    await session.flush()
