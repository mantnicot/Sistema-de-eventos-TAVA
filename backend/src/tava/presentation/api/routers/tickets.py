from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from tava.application.use_cases.tickets import TicketUseCase
from tava.domain.enums import UserRole
from tava.infrastructure.persistence.database import get_db
from tava.infrastructure.persistence.event_staff import can_access_event
from tava.infrastructure.persistence.models import TicketTypeModel
from tava.infrastructure.services.captcha import verify_captcha
from tava.presentation.api.dependencies import get_current_user, require_roles
from tava.presentation.api.schemas import PurchaseRequest, SellTicketRequest, TicketTypeCreateRequest

router = APIRouter(prefix="/tickets", tags=["Boletería"])


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
    uc = TicketUseCase(db)
    return await uc.list_my_tickets(user.id)


@router.get("/seller/mine")
async def seller_sales(
    user=Depends(require_roles(UserRole.SELLER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    uc = TicketUseCase(db)
    return await uc.list_seller_sales(user.id)


@router.get("/{ticket_id}/pdf")
async def download_ticket_pdf(
    ticket_id: UUID,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    uc = TicketUseCase(db)
    is_admin = user.role == UserRole.ADMIN
    try:
        pdf = await uc.get_ticket_pdf_bytes(ticket_id, user.id, is_admin)
    except ValueError as e:
        raise HTTPException(status_code=404 if "encontrada" in str(e).lower() else 403, detail=str(e))
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="boleta-{ticket_id}.pdf"'},
    )


@router.get("/orders/{order_id}/pdf")
async def download_order_pdf(
    order_id: UUID,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    uc = TicketUseCase(db)
    is_admin = user.role == UserRole.ADMIN
    is_seller = user.role in (UserRole.SELLER, UserRole.ADMIN)
    try:
        pdf = await uc.get_order_pdf_bytes(order_id, user.id, is_admin, is_seller)
    except ValueError as e:
        raise HTTPException(status_code=404 if "encontrada" in str(e).lower() else 403, detail=str(e))
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="boletas-{order_id}.pdf"'},
    )


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
    uc = TicketUseCase(db)
    try:
        return await uc.purchase_for_user(
            user_id=user.id,
            user_name=user.full_name,
            user_email=user.email,
            event_id=body.event_id,
            ticket_type_id=body.ticket_type_id,
            quantity=body.quantity,
            holder_names=body.holder_names,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/sell")
async def sell_tickets(
    body: SellTicketRequest,
    user=Depends(require_roles(UserRole.SELLER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    if not body.legal_accepted:
        raise HTTPException(status_code=400, detail="Debe aceptar los términos legales")
    if not await verify_captcha(body.captcha_token):
        raise HTTPException(status_code=400, detail="Captcha inválido")
    if user.role != UserRole.ADMIN and not await can_access_event(
        db, user.id, user.role, body.event_id, "seller"
    ):
        raise HTTPException(status_code=403, detail="No autorizado para vender en este evento")
    uc = TicketUseCase(db)
    try:
        return await uc.sell_as_seller(
            seller_id=user.id,
            seller_email=user.email,
            seller_name=user.full_name,
            buyer_email=body.buyer_email,
            event_id=body.event_id,
            ticket_type_id=body.ticket_type_id,
            quantity=body.quantity,
            holder_names=body.holder_names,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
