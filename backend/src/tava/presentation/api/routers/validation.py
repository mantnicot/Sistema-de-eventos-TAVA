from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from tava.application.use_cases.validation import ValidationUseCase
from tava.domain.enums import UserRole, ValidationResult
from tava.infrastructure.persistence.database import get_db
from tava.infrastructure.persistence.event_staff import can_access_event
from tava.presentation.api.dependencies import require_roles
from tava.presentation.api.schemas import ValidateQrRequest, ValidationResponse

router = APIRouter(prefix="/validation", tags=["Validación"])

MESSAGES = {
    ValidationResult.AUTHORIZED: "Acceso autorizado",
    ValidationResult.ALREADY_USED: "Boleta ya utilizada",
    ValidationResult.EVENT_DISABLED: "Evento no habilitado",
    ValidationResult.INVALID: "Boleta inválida",
    ValidationResult.NOT_AUTHORIZED: "No estás autorizado para validar este evento",
}


@router.post("/scan", response_model=ValidationResponse)
async def scan_qr(
    body: ValidateQrRequest,
    user=Depends(require_roles(UserRole.VALIDATOR, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    uc = ValidationUseCase(db)
    result, ticket = await uc.validate_qr(body.qr_token, user.id)
    return ValidationResponse(
        result=result.value,
        ticket_id=ticket.id if ticket else None,
        message=MESSAGES[result],
    )


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
