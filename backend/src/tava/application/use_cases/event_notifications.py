"""Notificaciones a asistentes por cambios de evento y gestión de boletas."""
from __future__ import annotations

import asyncio
from datetime import date, time
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from tava.config import get_settings
from tava.domain.enums import EventStatus, PaymentStatus
from tava.infrastructure.persistence.models import (
    EventModel,
    OrderModel,
    TicketModel,
    TicketTypeModel,
    UserModel,
)
from tava.infrastructure.security.ticket_tokens import generate_qr_token, generate_security_hash
from tava.infrastructure.services.email import (
    email_transport_ready,
    last_email_failure,
    send_event_broadcast_email,
    send_event_change_email,
    send_event_review_request_email,
    send_ticket_cancelled_email,
)
from tava.infrastructure.services.ticket_pdf import build_tickets_pdf

settings = get_settings()

MATERIAL_FIELDS = ("name", "event_date", "event_time", "city", "address", "status")


def _fmt_date(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def _fmt_time(t: time) -> str:
    return t.strftime("%H:%M")


def describe_event_changes(before: EventModel, after: EventModel) -> list[str]:
    changes: list[str] = []
    if before.name != after.name:
        changes.append(f"Nombre: «{before.name}» → «{after.name}»")
    if before.event_date != after.event_date:
        changes.append(f"Fecha: {_fmt_date(before.event_date)} → {_fmt_date(after.event_date)}")
    if before.event_time != after.event_time:
        changes.append(f"Hora: {_fmt_time(before.event_time)} → {_fmt_time(after.event_time)}")
    if before.city != after.city:
        changes.append(f"Ciudad: {before.city} → {after.city}")
    if before.address != after.address:
        changes.append(f"Dirección: {before.address} → {after.address}")
    if before.status != after.status:
        changes.append(f"Estado: {before.status.value} → {after.status.value}")
    return changes


class EventNotificationUseCase:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def notify_platform_admin_review_request(
        self,
        event: EventModel,
        *,
        organizer: UserModel | None = None,
    ) -> dict:
        if organizer is None:
            result = await self._session.execute(
                select(UserModel).where(UserModel.id == event.organizer_id)
            )
            organizer = result.scalar_one_or_none()
        if not organizer:
            return {"notified": False, "reason": "organizador_no_encontrado"}

        if not email_transport_ready():
            return {
                "notified": False,
                "reason": "correo_no_configurado",
                "email_error": last_email_failure() or None,
            }

        admins_result = await self._session.execute(
            select(UserModel).where(
                UserModel.is_platform_admin.is_(True),
                UserModel.is_active.is_(True),
            )
        )
        admins = list(admins_result.scalars().all())
        if not admins:
            return {"notified": False, "reason": "sin_admin_global"}

        admin_url = f"{settings.frontend_url.rstrip('/')}/admin"
        sent = 0
        last_err: str | None = None
        for admin in admins:
            ok = await send_event_review_request_email(
                admin.email,
                admin.full_name,
                event.name,
                organizer_name=organizer.full_name,
                organizer_email=organizer.email,
                event_date=_fmt_date(event.event_date),
                event_time=_fmt_time(event.event_time),
                city=event.city,
                category=event.category,
                admin_url=admin_url,
            )
            if ok:
                sent += 1
            else:
                last_err = last_email_failure() or last_err

        return {
            "notified": sent > 0,
            "reason": "envio_fallido" if sent == 0 else None,
            "emails_sent": sent,
            "recipients": len(admins),
            "email_error": last_err,
        }

    async def on_event_updated(self, before: EventModel, after: EventModel) -> dict:
        changes = describe_event_changes(before, after)
        if not changes:
            return {"notified": False, "reason": "sin_cambios_relevantes"}

        sold = await self._count_paid_tickets(after.id)
        if sold == 0:
            return {"notified": False, "reason": "sin_boletas_vendidas", "changes": changes}

        if not email_transport_ready():
            return {
                "notified": False,
                "reason": "correo_no_configurado",
                "changes": changes,
                "tickets_affected": sold,
                "email_error": last_email_failure() or None,
            }

        regenerated = await self._regenerate_unused_tickets(after.id)
        emails_sent = await self._email_all_orders(after, changes, include_pdf=True)
        await self._session.flush()
        failure = last_email_failure() if emails_sent == 0 else None
        return {
            "notified": emails_sent > 0,
            "reason": "envio_fallido" if emails_sent == 0 and sold > 0 else None,
            "changes": changes,
            "tickets_regenerated": regenerated,
            "emails_sent": emails_sent,
            "tickets_affected": sold,
            "email_error": failure,
        }

    async def broadcast_custom_email(
        self, event_id: UUID, *, subject: str, message: str
    ) -> dict:
        if not email_transport_ready():
            raise ValueError("Correo no configurado (Brevo/Resend). No se pudo enviar.")
        event = await self._load_event(event_id)
        buyers = await self._unique_buyers_for_event(event_id)
        if not buyers:
            return {"sent": 0, "message": "No hay asistentes con boletas pagadas"}
        sent = 0
        last_err: str | None = None
        for user in buyers:
            ok = await send_event_broadcast_email(
                user.email,
                user.full_name,
                event.name,
                subject.strip(),
                message.strip(),
            )
            if ok:
                sent += 1
            else:
                last_err = last_email_failure() or last_err
        return {"sent": sent, "recipients": len(buyers), "email_error": last_err}

    async def cancel_ticket(self, ticket_id: UUID, *, notify: bool = True) -> dict:
        result = await self._session.execute(
            select(TicketModel, OrderModel, EventModel, TicketTypeModel, UserModel)
            .join(OrderModel, TicketModel.order_id == OrderModel.id)
            .join(EventModel, TicketModel.event_id == EventModel.id)
            .join(TicketTypeModel, TicketModel.ticket_type_id == TicketTypeModel.id)
            .join(UserModel, TicketModel.owner_id == UserModel.id)
            .where(TicketModel.id == ticket_id)
        )
        row = result.one_or_none()
        if not row:
            raise ValueError("Boleta no encontrada")
        ticket, order, event, tt, owner = row
        if ticket.is_cancelled:
            raise ValueError("La boleta ya está cancelada")
        if ticket.is_used:
            raise ValueError("No se puede cancelar una boleta ya utilizada")

        ticket.is_cancelled = True
        if order.payment_status == PaymentStatus.PAID and not ticket.is_used:
            tt.quantity_available += 1

        emailed = False
        if notify and email_transport_ready():
            emailed = await send_ticket_cancelled_email(
                owner.email,
                owner.full_name,
                event.name,
                ticket.holder_name or owner.full_name,
                ticket.ticket_code,
            )
        await self._session.flush()
        return {
            "ticket_id": str(ticket.id),
            "cancelled": True,
            "stock_restored": order.payment_status == PaymentStatus.PAID,
            "email_sent": emailed,
        }

    async def _count_paid_tickets(self, event_id: UUID) -> int:
        result = await self._session.execute(
            select(TicketModel)
            .join(OrderModel, TicketModel.order_id == OrderModel.id)
            .where(
                TicketModel.event_id == event_id,
                OrderModel.payment_status == PaymentStatus.PAID,
                TicketModel.is_cancelled.is_(False),
            )
        )
        return len(result.scalars().all())

    async def _regenerate_unused_tickets(self, event_id: UUID) -> int:
        result = await self._session.execute(
            select(TicketModel)
            .join(OrderModel, TicketModel.order_id == OrderModel.id)
            .where(
                TicketModel.event_id == event_id,
                OrderModel.payment_status == PaymentStatus.PAID,
                TicketModel.is_cancelled.is_(False),
                TicketModel.is_used.is_(False),
            )
        )
        tickets = result.scalars().all()
        count = 0
        for ticket in tickets:
            ticket.qr_token = generate_qr_token()
            ticket.security_hash = generate_security_hash(
                ticket.id, ticket.event_id, ticket.qr_token, settings.jwt_secret_key
            )
            count += 1
        return count

    async def _email_all_orders(
        self, event: EventModel, changes: list[str], *, include_pdf: bool
    ) -> int:
        result = await self._session.execute(
            select(OrderModel)
            .where(
                OrderModel.event_id == event.id,
                OrderModel.payment_status == PaymentStatus.PAID,
            )
            .options(selectinload(OrderModel.tickets))
        )
        orders = result.scalars().all()
        sent = 0
        age = None
        if event.theatrical_details and isinstance(event.theatrical_details, dict):
            age = event.theatrical_details.get("age_rating")

        for order in orders:
            active_tickets = [t for t in order.tickets if not t.is_cancelled]
            if not active_tickets:
                continue
            buyer_result = await self._session.execute(
                select(UserModel).where(UserModel.id == order.buyer_id)
            )
            buyer = buyer_result.scalar_one_or_none()
            if not buyer:
                continue

            pdf_bytes = None
            if include_pdf:
                tt = await self._session.execute(
                    select(TicketTypeModel).where(
                        TicketTypeModel.id == active_tickets[0].ticket_type_id
                    )
                )
                ticket_type = tt.scalar_one_or_none()
                if ticket_type:
                    pdf_bytes = await asyncio.to_thread(
                        build_tickets_pdf,
                        event_name=event.name,
                        event_date=event.event_date,
                        event_time=event.event_time,
                        city=event.city,
                        address=event.address,
                        age_rating=age,
                        main_image_url=event.main_image_url,
                        ticket_type_name=ticket_type.name,
                        price=ticket_type.price,
                        tickets=[
                            (t.qr_token, t.holder_name or buyer.full_name, t.ticket_code or "")
                            for t in active_tickets
                            if not t.is_used
                        ]
                        or [
                            (t.qr_token, t.holder_name or buyer.full_name, t.ticket_code or "")
                            for t in active_tickets
                        ],
                    )

            ok = await send_event_change_email(
                buyer.email,
                buyer.full_name,
                event.name,
                changes,
                pdf_bytes=pdf_bytes,
                event_date=event.event_date.isoformat(),
                event_time=event.event_time.strftime("%H:%M"),
                frontend_url=settings.frontend_url.rstrip("/"),
            )
            if ok:
                sent += 1
        return sent

    async def _unique_buyers_for_event(self, event_id: UUID) -> list[UserModel]:
        result = await self._session.execute(
            select(UserModel)
            .join(OrderModel, OrderModel.buyer_id == UserModel.id)
            .where(
                OrderModel.event_id == event_id,
                OrderModel.payment_status == PaymentStatus.PAID,
            )
            .distinct()
        )
        return list(result.scalars().all())

    async def _load_event(self, event_id: UUID) -> EventModel:
        result = await self._session.execute(select(EventModel).where(EventModel.id == event_id))
        event = result.scalar_one_or_none()
        if not event:
            raise ValueError("Evento no encontrado")
        return event
