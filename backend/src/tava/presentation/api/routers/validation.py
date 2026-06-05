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
from tava.presentation.api.schemas import (
    AttendeesListResponse,
    AttendeeItem,
    ValidateQrRequest,
    ValidationResponse,
)

router = APIRouter(prefix="/validation", tags=["Validación"])

MESSAGES = {
    ValidationResult.AUTHORIZED: "Acceso autorizado",
    ValidationResult.ALREADY_USED: "Boleta ya utilizada",
    ValidationResult.EVENT_DISABLED: "Evento no habilitado",
    ValidationResult.INVALID: "Boleta inválida",
    ValidationResult.NOT_AUTHORIZED: "No estás autorizado para validar este evento",
}


async def _build_validation_response(
    db: AsyncSession, result: ValidationResult, ticket: TicketModel | None
) -> ValidationResponse:
    holder_name = None
    event_id = None
    event_name = None
    ingresados = None
    boletas_vendidas = None
    pendientes = None

    if ticket:
        holder_name = ticket.holder_name
        event_id = ticket.event_id
        ev_result = await db.execute(select(EventModel.name).where(EventModel.id == ticket.event_id))
        event_name = ev_result.scalar_one_or_none()
        uc = ValidationUseCase(db)
        stats = await uc.get_capacity_stats(ticket.event_id)
        if stats:
            ingresados = stats.get("ingresados")
            boletas_vendidas = stats.get("boletas_vendidas")
            pendientes = stats.get("pendientes_ingreso")

    return ValidationResponse(
        result=result.value,
        ticket_id=ticket.id if ticket else None,
        message=MESSAGES[result],
        holder_name=holder_name,
        event_id=event_id,
        event_name=event_name,
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
    uc = ValidationUseCase(db)
    result, ticket = await uc.validate_qr(body.qr_token, user.id, user.role)
    return await _build_validation_response(db, result, ticket)


@router.get("/aforo/{event_id}")
async def aforo(
    event_id: UUID,
    user=Depends(require_roles(UserRole.VALIDATOR, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    if not await can_access_event(db, user.id, user.role, event_id, "validator"):
        raise HTTPException(status_code=403, detail="No autorizado para este evento")
    uc = ValidationUseCase(db)
    stats = await uc.get_capacity_stats(event_id)
    if not stats:
        raise HTTPException(status_code=404, detail="Evento no encontrado")
    return stats


@router.get("/attendees/{event_id}", response_model=AttendeesListResponse)
async def list_attendees(
    event_id: UUID,
    user=Depends(require_roles(UserRole.VALIDATOR, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    if not await can_access_event(db, user.id, user.role, event_id, "validator"):
        raise HTTPException(status_code=403, detail="No autorizado para este evento")
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
