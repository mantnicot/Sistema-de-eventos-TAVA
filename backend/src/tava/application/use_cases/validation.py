from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tava.config import get_settings
from tava.domain.enums import EventStatus, UserRole, ValidationResult
from tava.infrastructure.persistence.event_staff import can_access_event
from tava.infrastructure.persistence.models import CheckInModel, EventModel, TicketModel
from tava.infrastructure.security.ticket_tokens import verify_security_hash

settings = get_settings()


class ValidationUseCase:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def validate_qr(
        self, qr_token: str, validator_id: UUID, user_role: UserRole
    ) -> tuple[ValidationResult, TicketModel | None]:
        result = await self._session.execute(select(TicketModel).where(TicketModel.qr_token == qr_token))
        ticket = result.scalar_one_or_none()
        if not ticket:
            return ValidationResult.INVALID, None

        if not verify_security_hash(
            ticket.id, ticket.event_id, ticket.qr_token, ticket.security_hash, settings.jwt_secret_key
        ):
            return ValidationResult.INVALID, None

        if not await can_access_event(
            self._session, validator_id, user_role, ticket.event_id, "validator"
        ):
            return ValidationResult.NOT_AUTHORIZED, ticket

        event_result = await self._session.execute(select(EventModel).where(EventModel.id == ticket.event_id))
        event = event_result.scalar_one_or_none()
        if not event or event.status not in (EventStatus.PUBLISHED, EventStatus.IN_PROGRESS):
            return ValidationResult.EVENT_DISABLED, ticket

        if ticket.is_used:
            return ValidationResult.ALREADY_USED, ticket

        ticket.is_used = True
        ticket.used_at = datetime.now(UTC)
        ticket.validated_by = validator_id
        self._session.add(
            CheckInModel(
                ticket_id=ticket.id,
                event_id=ticket.event_id,
                validator_id=validator_id,
                result=ValidationResult.AUTHORIZED.value,
            )
        )
        await self._session.flush()
        return ValidationResult.AUTHORIZED, ticket

    async def get_capacity_stats(self, event_id: UUID) -> dict:
        event_result = await self._session.execute(select(EventModel).where(EventModel.id == event_id))
        event = event_result.scalar_one_or_none()
        if not event:
            return {}
        entered = await self._session.execute(
            select(func.count()).select_from(TicketModel).where(
                TicketModel.event_id == event_id, TicketModel.is_used.is_(True)
            )
        )
        sold = await self._session.execute(
            select(func.count()).select_from(TicketModel).where(TicketModel.event_id == event_id)
        )
        ingresados = entered.scalar() or 0
        vendidos = sold.scalar() or 0
        capacidad = event.capacity
        return {
            "capacidad_total": capacidad,
            "ingresados": ingresados,
            "boletas_vendidas": vendidos,
            "pendientes_ingreso": max(vendidos - ingresados, 0),
            "disponibilidad": max(capacidad - ingresados, 0) if capacidad else None,
        }
