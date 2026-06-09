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

    async def _find_ticket(self, scan_value: str) -> TicketModel | None:
        scan_value = scan_value.strip()
        if not scan_value:
            return None

        if scan_value.isdigit() and 6 <= len(scan_value) <= 12:
            code = scan_value.zfill(8) if len(scan_value) <= 8 else scan_value
            result = await self._session.execute(
                select(TicketModel).where(TicketModel.ticket_code == code)
            )
            ticket = result.scalar_one_or_none()
            if ticket:
                return ticket

        result = await self._session.execute(
            select(TicketModel).where(TicketModel.qr_token == scan_value)
        )
        return result.scalar_one_or_none()

    async def _authorize_ticket(
        self, ticket: TicketModel, validator_id: UUID, user_role: UserRole
    ) -> tuple[ValidationResult, TicketModel | None]:
        if not verify_security_hash(
            ticket.id, ticket.event_id, ticket.qr_token, ticket.security_hash, settings.jwt_secret_key
        ):
            return ValidationResult.INVALID, None

        if not await can_access_event(
            self._session, validator_id, user_role, ticket.event_id, "validator"
        ):
            return ValidationResult.NOT_AUTHORIZED, ticket

        event_result = await self._session.execute(
            select(EventModel).where(EventModel.id == ticket.event_id)
        )
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

    async def validate_qr(
        self, qr_token: str, validator_id: UUID, user_role: UserRole
    ) -> tuple[ValidationResult, TicketModel | None]:
        ticket = await self._find_ticket(qr_token)
        if not ticket:
            return ValidationResult.INVALID, None
        return await self._authorize_ticket(ticket, validator_id, user_role)

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
            "event_name": event.name,
            "capacidad_total": capacidad,
            "ingresados": ingresados,
            "boletas_vendidas": vendidos,
            "pendientes_ingreso": max(vendidos - ingresados, 0),
            "disponibilidad": max(capacidad - ingresados, 0) if capacidad else None,
        }

    async def list_attendees(self, event_id: UUID) -> dict | None:
        event_result = await self._session.execute(select(EventModel).where(EventModel.id == event_id))
        event = event_result.scalar_one_or_none()
        if not event:
            return None
        tickets_result = await self._session.execute(
            select(TicketModel)
            .where(TicketModel.event_id == event_id)
            .order_by(TicketModel.is_used.desc(), TicketModel.holder_name.asc())
        )
        tickets = tickets_result.scalars().all()
        ingresados = sum(1 for t in tickets if t.is_used)
        return {
            "event_id": event_id,
            "event_name": event.name,
            "ingresados": ingresados,
            "boletas_vendidas": len(tickets),
            "pendientes_ingreso": max(len(tickets) - ingresados, 0),
            "attendees": [
                {
                    "ticket_id": t.id,
                    "holder_name": t.holder_name,
                    "ticket_code": t.ticket_code,
                    "is_used": t.is_used,
                    "used_at": t.used_at.isoformat() if t.used_at else None,
                }
                for t in tickets
            ],
        }
