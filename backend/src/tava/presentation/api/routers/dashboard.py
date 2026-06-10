from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tava.domain.enums import EventStatus, PaymentStatus, UserRole
from tava.infrastructure.persistence.database import get_db
from tava.infrastructure.persistence.models import EventModel, OrderModel, TicketModel
from tava.infrastructure.services.dashboard_report import build_kpis_pdf, build_kpis_xlsx
from tava.presentation.api.dependencies import require_roles

router = APIRouter(prefix="/dashboard", tags=["Dashboard Administrativo"])


async def _collect_kpis(db: AsyncSession) -> dict:
    active_events = await db.execute(
        select(func.count()).select_from(EventModel).where(
            EventModel.status.in_([EventStatus.PUBLISHED, EventStatus.IN_PROGRESS])
        )
    )
    sold_tickets = await db.execute(select(func.count()).select_from(TicketModel))
    revenue = await db.execute(
        select(func.coalesce(func.sum(OrderModel.total_amount), 0)).where(
            OrderModel.payment_status == PaymentStatus.PAID
        )
    )
    attendees = await db.execute(
        select(func.count()).select_from(TicketModel).where(TicketModel.is_used.is_(True))
    )
    orders = await db.execute(select(func.count()).select_from(OrderModel))
    total_orders = orders.scalar() or 0
    paid = await db.execute(
        select(func.count()).select_from(OrderModel).where(OrderModel.payment_status == PaymentStatus.PAID)
    )
    paid_count = paid.scalar() or 0
    conversion = (paid_count / total_orders * 100) if total_orders else 0

    return {
        "eventos_activos": active_events.scalar() or 0,
        "boletas_vendidas": sold_tickets.scalar() or 0,
        "ingresos": float(revenue.scalar() or 0),
        "asistentes": attendees.scalar() or 0,
        "conversion_porcentaje": round(conversion, 2),
    }


@router.get("/kpis")
async def kpis(
    user=Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    return await _collect_kpis(db)


@router.get("/report/pdf")
async def report_pdf(
    user=Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    data = await _collect_kpis(db)
    pdf = build_kpis_pdf(data)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="tava-metricas.pdf"'},
    )


@router.get("/report/xlsx")
async def report_xlsx(
    user=Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    data = await _collect_kpis(db)
    xlsx = build_kpis_xlsx(data)
    return Response(
        content=xlsx,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="tava-metricas.xlsx"'},
    )


@router.post("/test-email")
async def test_email(
    user=Depends(require_roles(UserRole.ADMIN)),
):
    from tava.infrastructure.services.email import (
        email_config_hint,
        email_transport_ready,
        last_email_failure,
        send_password_reset_email,
    )

    if not email_transport_ready():
        hint = email_config_hint() or last_email_failure()
        return {
            "success": False,
            "message": hint or "Correo no configurado en el servidor",
        }
    ok = await send_password_reset_email(
        user.email,
        user.full_name,
        "https://sistema-de-eventos-tava.vercel.app/restablecer-contrasena?token=test",
    )
    if ok:
        return {"success": True, "message": f"Correo de prueba enviado a {user.email}"}
    return {
        "success": False,
        "message": last_email_failure() or "No se pudo enviar el correo de prueba",
    }
