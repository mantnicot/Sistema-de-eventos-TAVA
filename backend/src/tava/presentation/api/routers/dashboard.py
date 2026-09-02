from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tava.domain.enums import EventStatus, PaymentStatus, UserRole
from tava.infrastructure.persistence.database import get_db
from tava.infrastructure.persistence.models import EventModel, OrderModel, TicketModel
from tava.infrastructure.services.dashboard_report import build_kpis_pdf, build_kpis_xlsx
from tava.presentation.api.platform_auth import is_platform_admin, require_platform_admin

router = APIRouter(prefix="/dashboard", tags=["Dashboard Administrativo"])


async def _collect_kpis(db: AsyncSession, event_id: UUID | None = None) -> dict:
    event = None
    if event_id:
        event_result = await db.execute(select(EventModel).where(EventModel.id == event_id))
        event = event_result.scalar_one_or_none()

    active_events_query = select(func.count()).select_from(EventModel).where(
        EventModel.status.in_([EventStatus.PUBLISHED, EventStatus.IN_PROGRESS])
    )
    tickets_filter = [TicketModel.is_cancelled.is_(False)]
    orders_filter = []
    if event_id:
        active_events_query = active_events_query.where(EventModel.id == event_id)
        tickets_filter.append(TicketModel.event_id == event_id)
        orders_filter.append(OrderModel.event_id == event_id)

    active_events = await db.execute(active_events_query)
    sold_tickets = await db.execute(
        select(func.count()).select_from(TicketModel).where(*tickets_filter)
    )
    revenue = await db.execute(
        select(func.coalesce(func.sum(OrderModel.total_amount), 0)).where(
            OrderModel.payment_status == PaymentStatus.PAID,
            *orders_filter,
        )
    )
    attendees = await db.execute(
        select(func.count()).select_from(TicketModel).where(
            TicketModel.is_used.is_(True),
            *tickets_filter,
        )
    )
    orders = await db.execute(
        select(func.count()).select_from(OrderModel).where(*orders_filter)
    )
    total_orders = orders.scalar() or 0
    paid = await db.execute(
        select(func.count()).select_from(OrderModel).where(
            OrderModel.payment_status == PaymentStatus.PAID,
            *orders_filter,
        )
    )
    paid_count = paid.scalar() or 0
    conversion = (paid_count / total_orders * 100) if total_orders else 0
    sold_count = sold_tickets.scalar() or 0
    attendee_count = attendees.scalar() or 0
    capacity = event.capacity if event else 0
    occupancy = (sold_count / capacity * 100) if capacity else 0

    return {
        "scope": "event" if event else "general",
        "event_id": str(event.id) if event else None,
        "event_name": event.name if event else None,
        "event_date": event.event_date.isoformat() if event else None,
        "event_status": event.status.value if event else None,
        "capacity": capacity,
        "eventos_activos": active_events.scalar() or 0,
        "boletas_vendidas": sold_count,
        "ingresos": float(revenue.scalar() or 0),
        "asistentes": attendee_count,
        "pendientes_ingreso": max(0, sold_count - attendee_count),
        "ocupacion_porcentaje": round(occupancy, 2),
        "ordenes_totales": total_orders,
        "ordenes_pagadas": paid_count,
        "conversion_porcentaje": round(conversion, 2),
    }


@router.get("/kpis")
async def kpis(
    event_id: UUID | None = None,
    user=Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    return await _collect_kpis(db, event_id)


@router.get("/report/pdf")
async def report_pdf(
    event_id: UUID | None = None,
    user=Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    data = await _collect_kpis(db, event_id)
    pdf = build_kpis_pdf(data)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="tava-metricas.pdf"'},
    )


@router.get("/report/xlsx")
async def report_xlsx(
    event_id: UUID | None = None,
    user=Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    data = await _collect_kpis(db, event_id)
    xlsx = build_kpis_xlsx(data)
    return Response(
        content=xlsx,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="tava-metricas.xlsx"'},
    )


@router.post("/test-email")
async def test_email(
    user=Depends(require_platform_admin),
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
