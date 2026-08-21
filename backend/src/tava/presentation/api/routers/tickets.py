from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from tava.application.use_cases.ticket_emails import send_order_confirmation_email_background
from tava.application.use_cases.tickets import TicketUseCase
from tava.domain.enums import UserRole
from tava.infrastructure.persistence.database import get_db
from tava.infrastructure.persistence.event_staff import can_access_event
from tava.infrastructure.persistence.models import TicketTypeModel
from tava.presentation.api.dependencies import get_current_user, require_roles
from tava.presentation.api.schemas import (
    AdminIssueTicketsRequest,
    ClaimTicketsRequest,
    PurchaseRequest,
    SellTicketRequest,
    TicketTypeCreateRequest,
    CancelTicketRequest,
)

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


@router.post("/claim-code")
async def claim_tickets(
    body: ClaimTicketsRequest,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    uc = TicketUseCase(db)
    try:
        result = await uc.claim_order_by_code(user.id, body.code)
        await db.commit()
        return result
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/admin/issue-claim")
async def admin_issue_claim_tickets(
    body: AdminIssueTicketsRequest,
    user=Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    uc = TicketUseCase(db)
    try:
        result = await uc.issue_claim_order_as_admin(
            admin_id=user.id,
            buyer_name=body.buyer_name,
            buyer_email=str(body.buyer_email),
            event_id=body.event_id,
            ticket_type_id=body.ticket_type_id,
            quantity=body.quantity,
            holder_names=body.holder_names,
        )
        await db.commit()
        return result
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/seller/mine")
async def seller_sales(
    user=Depends(require_roles(UserRole.SELLER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    uc = TicketUseCase(db)
    return await uc.list_seller_sales(user.id)


@router.get("/sales")
async def sales_ledger(
    event_id: UUID | None = None,
    user=Depends(require_roles(UserRole.SELLER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """Lista de personas y boletas vendidas (admin: todas; vendedor: propias o de eventos que organiza)."""
    uc = TicketUseCase(db)
    return await uc.list_sales_ledger(user_id=user.id, user_role=user.role, event_id=event_id)


@router.post("/admin/{ticket_id}/cancel")
async def admin_cancel_ticket(
    ticket_id: UUID,
    body: CancelTicketRequest | None = None,
    _user=Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    from tava.application.use_cases.event_notifications import EventNotificationUseCase

    notify = body.notify_holder if body else True
    uc = EventNotificationUseCase(db)
    try:
        result = await uc.cancel_ticket(ticket_id, notify=notify)
        await db.commit()
        return result
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/admin/orders/{order_id}/resend-email")
async def admin_resend_order_email(
    order_id: UUID,
    _user=Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    try:
        sent = await TicketUseCase(db).send_order_confirmation_email(order_id)
        if not sent:
            raise HTTPException(status_code=404, detail="La orden no tiene boletas para reenviar")
        return {
            "email_sent": True,
            "order_id": str(order_id),
            "message": "El proveedor confirmó el reenvío de las boletas.",
        }
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except Exception:
        raise HTTPException(status_code=500, detail="No se pudo reenviar el correo de boletas")


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


@router.post("/purchase")
async def purchase(
    body: PurchaseRequest,
    background_tasks: BackgroundTasks,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not body.legal_accepted:
        raise HTTPException(status_code=400, detail="Debe aceptar los términos legales")
    uc = TicketUseCase(db)
    try:
        result = await uc.purchase_for_user(
            user_id=user.id,
            user_name=user.full_name,
            user_email=user.email,
            event_id=body.event_id,
            ticket_type_id=body.ticket_type_id,
            quantity=body.quantity,
            holder_names=body.holder_names,
            seat_ids=body.seat_ids,
        )
        await db.commit()
        if result.get("email_pending") and result.get("order_id"):
            background_tasks.add_task(
                send_order_confirmation_email_background,
                UUID(str(result["order_id"])),
            )
        return result
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/sell")
async def sell_tickets(
    body: SellTicketRequest,
    user=Depends(require_roles(UserRole.SELLER, UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    if not body.legal_accepted:
        raise HTTPException(status_code=400, detail="Debe aceptar los términos legales")
    if user.role != UserRole.ADMIN and not await can_access_event(
        db, user.id, user.role, body.event_id, "seller"
    ):
        raise HTTPException(status_code=403, detail="No autorizado para vender en este evento")
    uc = TicketUseCase(db)
    try:
        result = await uc.sell_as_seller(
            seller_id=user.id,
            seller_email=user.email,
            seller_name=user.full_name,
            buyer_email=body.buyer_email,
            event_id=body.event_id,
            ticket_type_id=body.ticket_type_id,
            quantity=body.quantity,
            holder_names=body.holder_names,
        )
        await db.commit()
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    email_sent = False
    email_error: str | None = None
    if result.get("email_pending") and result.get("order_id"):
        try:
            email_sent = await uc.send_order_confirmation_email(
                UUID(str(result["order_id"]))
            )
        except Exception as exc:
            email_error = str(exc) or "El proveedor de correo no confirmó el envío."

    result["email_pending"] = False
    result["email_sent"] = email_sent
    result["email_error"] = email_error
    result["message"] = (
        "Venta registrada y correo confirmado por el proveedor."
        if email_sent
        else "Venta registrada, pero el proveedor no confirmó el correo."
    )
    return result
