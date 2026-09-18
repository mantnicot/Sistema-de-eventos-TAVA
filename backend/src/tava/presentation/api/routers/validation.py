from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tava.application.use_cases.validation import ValidationUseCase
from tava.domain.enums import UserRole, ValidationResult
from tava.infrastructure.persistence.database import get_db
from tava.infrastructure.persistence.event_staff import can_access_event
from tava.infrastructure.persistence.models import EventModel, TicketModel
from tava.presentation.api.dependencies import require_roles
from tava.presentation.api.auth_helpers import can_manage_event, is_platform_admin
from tava.presentation.api.schemas import (
    AttendeesListResponse,
    AttendeeItem,
    ValidateQrRequest,
    ValidationResponse,
)

router = APIRouter(prefix="/validation", tags=["Validación"])

MESSAGES = {
    ValidationResult.AUTHORIZED: "Permiso autorizado",
    ValidationResult.ALREADY_USED: "Boleta ya utilizada",
    ValidationResult.CANCELLED: "Boleta cancelada",
    ValidationResult.EVENT_DISABLED: "Ingreso bloqueado o evento no habilitado",
    ValidationResult.INVALID: "Boleta no válida",
    ValidationResult.NOT_AUTHORIZED: "No estás autorizado para validar este evento",
    ValidationResult.WRONG_EVENT: "No corresponde a este evento",
}


async def _require_event_ops_access(db: AsyncSession, user, event_id: UUID, staff_role: str) -> None:
    if is_platform_admin(user):
        return
    if user.role == UserRole.ORGANIZER:
        result = await db.execute(select(EventModel).where(EventModel.id == event_id))
        event = result.scalar_one_or_none()
        if event and can_manage_event(user, event):
            return
        raise HTTPException(status_code=403, detail="No autorizado para este evento")
    if not await can_access_event(
        db, user.id, user.role, event_id, staff_role, is_platform_admin=is_platform_admin(user)
    ):
        raise HTTPException(status_code=403, detail="No autorizado para este evento")


async def _build_validation_response(
    db: AsyncSession,
    result: ValidationResult,
    ticket: TicketModel | None,
    *,
    selected_event_id: UUID | None = None,
) -> ValidationResponse:
    holder_name = None
    ticket_code = None
    event_id = selected_event_id
    event_name = None
    ticket_event_name = None
    ingresados = None
    boletas_vendidas = None
    pendientes = None

    if ticket:
        holder_name = ticket.holder_name
        ticket_code = ticket.ticket_code
        ticket_event_name_row = await db.execute(
            select(EventModel.name).where(EventModel.id == ticket.event_id)
        )
        ticket_event_name = ticket_event_name_row.scalar_one_or_none()

    stats_event_id = selected_event_id or (ticket.event_id if ticket else None)
    if stats_event_id:
        event_id = stats_event_id
        ev_result = await db.execute(select(EventModel.name).where(EventModel.id == stats_event_id))
        event_name = ev_result.scalar_one_or_none()
        uc = ValidationUseCase(db)
        stats = await uc.get_capacity_stats(stats_event_id)
        if stats:
            ingresados = stats.get("ingresados")
            boletas_vendidas = stats.get("boletas_vendidas")
            pendientes = stats.get("pendientes_ingreso")

    message = MESSAGES[result]
    if result == ValidationResult.WRONG_EVENT and ticket_event_name:
        message = f"No corresponde a este evento (es de: {ticket_event_name})"
    elif result == ValidationResult.ALREADY_USED and holder_name:
        message = f"Boleta ya utilizada — {holder_name}"
    elif result == ValidationResult.AUTHORIZED and holder_name:
        message = f"Permiso autorizado — {holder_name}"

    return ValidationResponse(
        result=result.value,
        ticket_id=ticket.id if ticket else None,
        message=message,
        holder_name=holder_name,
        ticket_code=ticket_code,
        event_id=event_id,
        event_name=event_name,
        ticket_event_name=ticket_event_name,
        ingresados=ingresados,
        boletas_vendidas=boletas_vendidas,
        pendientes_ingreso=pendientes,
    )


@router.post("/scan", response_model=ValidationResponse)
async def scan_qr(
    body: ValidateQrRequest,
    user=Depends(require_roles(UserRole.VALIDATOR, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    if body.event_id is not None:
        await _require_event_ops_access(db, user, body.event_id, "validator")
    uc = ValidationUseCase(db)
    result, ticket = await uc.validate_qr(
        body.qr_token,
        user.id,
        user.role,
        expected_event_id=body.event_id,
    )
    return await _build_validation_response(
        db, result, ticket, selected_event_id=body.event_id
    )


@router.get("/aforo/{event_id}")
async def aforo(
    event_id: UUID,
    user=Depends(require_roles(UserRole.VALIDATOR, UserRole.ADMIN, UserRole.ORGANIZER)),
    db: AsyncSession = Depends(get_db),
):
    await _require_event_ops_access(db, user, event_id, "validator")
    uc = ValidationUseCase(db)
    stats = await uc.get_capacity_stats(event_id)
    if not stats:
        raise HTTPException(status_code=404, detail="Evento no encontrado")
    return stats


@router.get("/attendees/{event_id}", response_model=AttendeesListResponse)
async def list_attendees(
    event_id: UUID,
    user=Depends(require_roles(UserRole.VALIDATOR, UserRole.ADMIN, UserRole.ORGANIZER)),
    db: AsyncSession = Depends(get_db),
):
    await _require_event_ops_access(db, user, event_id, "validator")
    uc = ValidationUseCase(db)
    data = await uc.list_attendees(event_id)
    if not data:
        raise HTTPException(status_code=404, detail="Evento no encontrado")
    return AttendeesListResponse(
        event_id=data["event_id"],
        event_name=data["event_name"],
        ingresados=data["ingresados"],
        boletas_vendidas=data["boletas_vendidas"],
        pendientes_ingreso=data["pendientes_ingreso"],
        attendees=[AttendeeItem(**a) for a in data["attendees"]],
    )
