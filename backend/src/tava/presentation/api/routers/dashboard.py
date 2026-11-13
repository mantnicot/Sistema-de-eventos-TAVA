from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tava.domain.enums import EventStatus, PaymentStatus
from tava.infrastructure.persistence.database import get_db
from tava.infrastructure.persistence.models import EventModel, OrderModel, TicketModel, TicketTypeModel
from tava.infrastructure.services.dashboard_report import build_kpis_pdf, build_kpis_xlsx
from tava.presentation.api.auth_helpers import is_platform_admin
from tava.presentation.api.platform_auth import require_event_manager, require_platform_admin

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


def _money(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.01")))


@router.get("/organizer-report")
async def organizer_report(
    event_id: UUID | None = None,
    user=Depends(require_event_manager),
    db: AsyncSession = Depends(get_db),
):
    """Boletas, asistentes y reparto de comisión de los eventos del organizador."""
    events_query = select(EventModel).order_by(EventModel.event_date.desc())
    if not is_platform_admin(user):
        events_query = events_query.where(EventModel.organizer_id == user.id)
    if event_id:
        events_query = events_query.where(EventModel.id == event_id)
    events = list((await db.execute(events_query)).scalars().all())
    if event_id and not events:
        raise HTTPException(status_code=404, detail="Evento no encontrado")

    event_ids = [event.id for event in events]
    rows = []
    if event_ids:
        ticket_rows = await db.execute(
            select(TicketModel, TicketTypeModel, EventModel, OrderModel)
            .join(TicketTypeModel, TicketModel.ticket_type_id == TicketTypeModel.id)
            .join(EventModel, TicketModel.event_id == EventModel.id)
            .join(OrderModel, TicketModel.order_id == OrderModel.id)
            .where(
                TicketModel.event_id.in_(event_ids),
                OrderModel.payment_status == PaymentStatus.PAID,
            )
            .order_by(EventModel.event_date.desc(), TicketModel.holder_name.asc())
        )
        rows = ticket_rows.all()

    per_event: dict[UUID, dict] = {}
    for event in events:
        rate = Decimal(str(event.commission_rate)) if event.commission_rate is not None else None
        per_event[event.id] = {
            "event_id": str(event.id),
            "event_name": event.name,
            "event_date": event.event_date.isoformat(),
            "commission_rate": float(rate) if rate is not None else None,
            "boletas_vendidas": 0,
            "ingresados": 0,
            "bruto": Decimal("0"),
            "comision_sistema": Decimal("0"),
            "neto_organizador": Decimal("0"),
        }

    attendees = []
    for ticket, ticket_type, event, _order in rows:
        price = Decimal(str(ticket_type.price or 0))
        rate = Decimal(str(event.commission_rate)) if event.commission_rate is not None else Decimal("0")
        fee = (price * rate).quantize(Decimal("0.01"))
        net = (price - fee).quantize(Decimal("0.01"))
        bucket = per_event[event.id]
        if not ticket.is_cancelled:
            bucket["boletas_vendidas"] += 1
            bucket["bruto"] += price
            bucket["comision_sistema"] += fee
            bucket["neto_organizador"] += net
            if ticket.is_used:
                bucket["ingresados"] += 1
        attendees.append(
            {
                "ticket_id": str(ticket.id),
                "event_id": str(event.id),
                "event_name": event.name,
                "holder_name": ticket.holder_name,
                "ticket_code": ticket.ticket_code,
                "is_used": bool(ticket.is_used),
                "is_cancelled": bool(ticket.is_cancelled),
                "price": _money(price),
                "comision_sistema": _money(Decimal("0") if ticket.is_cancelled else fee),
                "neto_organizador": _money(Decimal("0") if ticket.is_cancelled else net),
            }
        )

    event_rows = []
    bruto = Decimal("0")
    fee_total = Decimal("0")
    net_total = Decimal("0")
    sold = 0
    entered = 0
    for bucket in per_event.values():
        sold += bucket["boletas_vendidas"]
        entered += bucket["ingresados"]
        bruto += bucket["bruto"]
        fee_total += bucket["comision_sistema"]
        net_total += bucket["neto_organizador"]
        event_rows.append(
            {
                **bucket,
                "pendientes_ingreso": max(0, bucket["boletas_vendidas"] - bucket["ingresados"]),
                "bruto": _money(bucket["bruto"]),
                "comision_sistema": _money(bucket["comision_sistema"]),
                "neto_organizador": _money(bucket["neto_organizador"]),
            }
        )

    single = events[0] if event_id and len(events) == 1 else None
    configured_rates = {
        Decimal(str(event.commission_rate)) if event.commission_rate is not None else Decimal("0")
        for event in events
    }
    shared_rate = configured_rates.pop() if len(configured_rates) == 1 else None
    return {
        "event_id": str(single.id) if single else None,
        "event_name": single.name if single else None,
        "commission_rate": float(shared_rate) if shared_rate is not None else None,
        "boletas_vendidas": sold,
        "ingresados": entered,
        "pendientes_ingreso": max(0, sold - entered),
        "bruto": _money(bruto),
        "comision_sistema": _money(fee_total),
        "neto_organizador": _money(net_total),
        "events": event_rows,
        "attendees": attendees,
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
