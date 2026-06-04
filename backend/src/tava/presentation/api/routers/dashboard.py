from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tava.domain.enums import EventStatus, PaymentStatus, UserRole
from tava.infrastructure.persistence.database import get_db
from tava.infrastructure.persistence.models import EventModel, OrderModel, TicketModel
from tava.presentation.api.dependencies import require_roles

router = APIRouter(prefix="/dashboard", tags=["Dashboard Administrativo"])


@router.get("/kpis")
async def kpis(
    user=Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
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
