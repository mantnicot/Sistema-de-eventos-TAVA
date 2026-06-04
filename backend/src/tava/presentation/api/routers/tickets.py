from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tava.application.use_cases.loyalty import LoyaltyUseCase
from tava.config import get_settings
from tava.domain.enums import PaymentStatus, UserRole
from tava.infrastructure.persistence.database import get_db
from tava.infrastructure.persistence.models import OrderModel, TicketModel, TicketTypeModel
from tava.infrastructure.security.ticket_tokens import generate_qr_token, generate_security_hash
from tava.infrastructure.services.captcha import verify_captcha
from tava.presentation.api.dependencies import get_current_user, require_roles
from tava.presentation.api.schemas import PurchaseRequest, TicketTypeCreateRequest

router = APIRouter(prefix="/tickets", tags=["Boletería"])
settings = get_settings()


@router.post("/types")
async def create_ticket_type(
    body: TicketTypeCreateRequest,
    user=Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    tt = TicketTypeModel(**body.model_dump())
    db.add(tt)
    await db.flush()
    await db.refresh(tt)
    return {"id": str(tt.id), "name": tt.name, "price": float(tt.price)}


@router.get("/mine")
async def my_tickets(user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(TicketModel).where(TicketModel.owner_id == user.id).order_by(TicketModel.id.desc())
    )
    tickets = result.scalars().all()
    return [
        {
            "id": str(t.id),
            "event_id": str(t.event_id),
            "qr_token": t.qr_token,
            "is_used": t.is_used,
        }
        for t in tickets
    ]


@router.post("/purchase")
async def purchase(
    body: PurchaseRequest,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not body.legal_accepted:
        raise HTTPException(status_code=400, detail="Debe aceptar los términos legales")
    if not await verify_captcha(body.captcha_token):
        raise HTTPException(status_code=400, detail="Captcha inválido")

    tt_result = await db.execute(select(TicketTypeModel).where(TicketTypeModel.id == body.ticket_type_id))
    ticket_type = tt_result.scalar_one_or_none()
    if not ticket_type or ticket_type.event_id != body.event_id:
        raise HTTPException(status_code=404, detail="Tipo de boleta no encontrado")
    if ticket_type.quantity_available < body.quantity:
        raise HTTPException(status_code=400, detail="Cantidad no disponible")

    total = ticket_type.price * body.quantity
    order = OrderModel(
        buyer_id=user.id,
        event_id=body.event_id,
        total_amount=total,
        payment_status=PaymentStatus.PENDING,
        legal_accepted=True,
    )
    db.add(order)
    await db.flush()

    created = []
    for _ in range(body.quantity):
        qr = generate_qr_token()
        ticket = TicketModel(
            order_id=order.id,
            ticket_type_id=ticket_type.id,
            owner_id=user.id,
            event_id=body.event_id,
            qr_token=qr,
            security_hash="",
        )
        db.add(ticket)
        await db.flush()
        ticket.security_hash = generate_security_hash(
            ticket.id, ticket.event_id, ticket.qr_token, settings.jwt_secret_key
        )
        created.append(ticket)

    ticket_type.quantity_available -= body.quantity
    loyalty = LoyaltyUseCase(db)
    lamina = f"/uploads/laminas/{body.event_id}.png"
    await loyalty.grant_collectible(user.id, body.event_id, lamina)

    return {
        "order_id": str(order.id),
        "total": float(total),
        "payment_status": order.payment_status.value,
        "tickets": [{"id": str(t.id), "qr_token": t.qr_token} for t in created],
        "message": "Compra registrada. Complete el pago en la pasarela.",
    }
