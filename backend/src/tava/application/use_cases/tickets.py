from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from tava.application.use_cases.loyalty import LoyaltyUseCase
from tava.config import get_settings
from tava.domain.enums import PaymentProvider, PaymentStatus
from tava.infrastructure.persistence.models import EventModel, OrderModel, TicketModel, TicketTypeModel, UserModel
from tava.infrastructure.persistence.repositories.sqlalchemy_user_repository import SQLAlchemyUserRepository
from tava.infrastructure.security.ticket_codes import assign_unique_ticket_code, backfill_missing_ticket_codes
from tava.infrastructure.security.ticket_tokens import generate_qr_token, generate_security_hash
from tava.infrastructure.services.email import last_email_failure, send_tickets_confirmation_email
from tava.infrastructure.services.ticket_pdf import build_tickets_pdf

settings = get_settings()


class TicketUseCase:
    def __init__(self, session: AsyncSession):
        self._session = session
        self._users = SQLAlchemyUserRepository(session)

    async def _load_event(self, event_id: UUID) -> EventModel:
        result = await self._session.execute(select(EventModel).where(EventModel.id == event_id))
        event = result.scalar_one_or_none()
        if not event:
            raise ValueError("Evento no encontrado")
        return event

    async def _load_ticket_type(self, ticket_type_id: UUID, event_id: UUID) -> TicketTypeModel:
        result = await self._session.execute(
            select(TicketTypeModel).where(TicketTypeModel.id == ticket_type_id)
        )
        tt = result.scalar_one_or_none()
        if not tt or tt.event_id != event_id:
            raise ValueError("Tipo de boleta no encontrado")
        return tt

    def _normalize_holder_names(self, quantity: int, holder_names: list[str] | None, fallback: str) -> list[str]:
        if holder_names and len(holder_names) == quantity:
            return [n.strip() for n in holder_names]
        if holder_names and len(holder_names) == 1:
            return [holder_names[0].strip()] * quantity
        return [fallback] * quantity

    async def create_order(
        self,
        *,
        event_id: UUID,
        ticket_type_id: UUID,
        quantity: int,
        buyer_id: UUID,
        seller_id: UUID | None,
        holder_names: list[str] | None,
        buyer_display_name: str,
        mark_paid: bool,
    ) -> tuple[OrderModel, list[TicketModel], EventModel, TicketTypeModel]:
        if quantity < 1 or quantity > 20:
            raise ValueError("Cantidad inválida (1-20)")
        event = await self._load_event(event_id)
        ticket_type = await self._load_ticket_type(ticket_type_id, event_id)
        if ticket_type.quantity_available < quantity:
            raise ValueError("Cantidad no disponible")

        names = self._normalize_holder_names(quantity, holder_names, buyer_display_name)
        total = ticket_type.price * quantity
        order = OrderModel(
            buyer_id=buyer_id,
            seller_id=seller_id,
            event_id=event_id,
            total_amount=total,
            payment_status=PaymentStatus.PAID if mark_paid else PaymentStatus.PENDING,
            payment_provider=PaymentProvider.MANUAL if seller_id else PaymentProvider.MANUAL,
            legal_accepted=True,
        )
        self._session.add(order)
        await self._session.flush()

        created: list[TicketModel] = []
        for name in names:
            qr = generate_qr_token()
            ticket = TicketModel(
                order_id=order.id,
                ticket_type_id=ticket_type.id,
                owner_id=buyer_id,
                event_id=event_id,
                holder_name=name,
                qr_token=qr,
                ticket_code=await assign_unique_ticket_code(self._session),
                security_hash="",
            )
            self._session.add(ticket)
            await self._session.flush()
            ticket.security_hash = generate_security_hash(
                ticket.id, ticket.event_id, ticket.qr_token, settings.jwt_secret_key
            )
            created.append(ticket)

        ticket_type.quantity_available -= quantity
        lamina = event.main_image_url or f"/uploads/laminas/{event_id}.png"
        await LoyaltyUseCase(self._session).grant_collectible(buyer_id, event_id, lamina)
        await self._session.flush()
        return order, created, event, ticket_type

    async def _send_pdf_emails(
        self,
        order: OrderModel,
        tickets: list[TicketModel],
        event: EventModel,
        ticket_type: TicketTypeModel,
        buyer: UserModel,
        seller: UserModel | None,
    ) -> None:
        age = None
        if event.theatrical_details and isinstance(event.theatrical_details, dict):
            age = event.theatrical_details.get("age_rating")
        pdf = build_tickets_pdf(
            event_name=event.name,
            event_date=event.event_date,
            event_time=event.event_time,
            city=event.city,
            address=event.address,
            age_rating=age,
            main_image_url=event.main_image_url,
            ticket_type_name=ticket_type.name,
            price=ticket_type.price,
            tickets=[(t.qr_token, t.holder_name or buyer.full_name, t.ticket_code or "") for t in tickets],
        )
        ok_buyer = await send_tickets_confirmation_email(
            buyer.email,
            buyer.full_name,
            event.name,
            len(tickets),
            pdf,
            is_seller_copy=False,
            event_date=event.event_date.isoformat(),
            event_time=event.event_time.strftime("%H:%M"),
        )
        if not ok_buyer:
            raise ValueError(last_email_failure() or "No se pudo enviar el correo al comprador")
        if seller and seller.email.lower() != buyer.email.lower():
            await send_tickets_confirmation_email(
                seller.email,
                seller.full_name,
                event.name,
                len(tickets),
                pdf,
                is_seller_copy=True,
                event_date=event.event_date.isoformat(),
                event_time=event.event_time.strftime("%H:%M"),
            )

    async def purchase_for_user(
        self,
        user_id: UUID,
        user_name: str,
        user_email: str,
        event_id: UUID,
        ticket_type_id: UUID,
        quantity: int,
        holder_names: list[str] | None,
    ) -> dict:
        order, tickets, event, tt = await self.create_order(
            event_id=event_id,
            ticket_type_id=ticket_type_id,
            quantity=quantity,
            buyer_id=user_id,
            seller_id=None,
            holder_names=holder_names,
            buyer_display_name=user_name,
            mark_paid=True,
        )
        buyer_model = await self._users.get_model_by_email(user_email)
        if buyer_model:
            try:
                await self._send_pdf_emails(order, tickets, event, tt, buyer_model, None)
            except ValueError:
                await self._session.rollback()
                raise
        return self._order_response(order, tickets, event, tt)

    async def sell_as_seller(
        self,
        seller_id: UUID,
        seller_email: str,
        seller_name: str,
        buyer_email: str,
        event_id: UUID,
        ticket_type_id: UUID,
        quantity: int,
        holder_names: list[str],
    ) -> dict:
        buyer = await self._users.get_model_by_email(buyer_email)
        if not buyer:
            raise ValueError("El comprador debe tener cuenta registrada con ese correo")
        seller = await self._users.get_model_by_email(seller_email)
        order, tickets, event, tt = await self.create_order(
            event_id=event_id,
            ticket_type_id=ticket_type_id,
            quantity=quantity,
            buyer_id=buyer.id,
            seller_id=seller_id,
            holder_names=holder_names,
            buyer_display_name=buyer.full_name,
            mark_paid=True,
        )
        buyer_model = await self._users.get_model_by_email(buyer_email)
        seller_model = await self._users.get_model_by_email(seller_email)
        if buyer_model and seller_model:
            try:
                await self._send_pdf_emails(order, tickets, event, tt, buyer_model, seller_model)
            except ValueError:
                await self._session.rollback()
                raise
        return self._order_response(order, tickets, event, tt)

    def _order_response(
        self, order: OrderModel, tickets: list[TicketModel], event: EventModel, tt: TicketTypeModel
    ) -> dict:
        return {
            "order_id": str(order.id),
            "total": float(order.total_amount),
            "payment_status": order.payment_status.value,
            "event_name": event.name,
            "ticket_type": tt.name,
            "tickets": [
                {
                    "id": str(t.id),
                    "holder_name": t.holder_name,
                    "qr_token": t.qr_token,
                }
                for t in tickets
            ],
            "pdf_url": f"/tickets/orders/{order.id}/pdf",
            "message": "Boletas generadas. Revisa tu correo con el PDF adjunto.",
        }

    async def get_order_pdf_bytes(self, order_id: UUID, user_id: UUID, is_admin: bool, is_seller: bool) -> bytes:
        result = await self._session.execute(
            select(OrderModel)
            .where(OrderModel.id == order_id)
            .options(selectinload(OrderModel.tickets))
        )
        order = result.scalar_one_or_none()
        if not order:
            raise ValueError("Orden no encontrada")
        if not is_admin and order.buyer_id != user_id and order.seller_id != user_id:
            raise ValueError("No autorizado")
        event = await self._load_event(order.event_id)
        if not order.tickets:
            raise ValueError("Sin boletas en la orden")
        tt = await self._load_ticket_type(order.tickets[0].ticket_type_id, order.event_id)
        age = None
        if event.theatrical_details and isinstance(event.theatrical_details, dict):
            age = event.theatrical_details.get("age_rating")
        return build_tickets_pdf(
            event_name=event.name,
            event_date=event.event_date,
            event_time=event.event_time,
            city=event.city,
            address=event.address,
            age_rating=age,
            main_image_url=event.main_image_url,
            ticket_type_name=tt.name,
            price=tt.price,
            tickets=[(t.qr_token, t.holder_name or "", t.ticket_code or "") for t in order.tickets],
        )

    async def list_my_tickets(self, user_id: UUID) -> list[dict]:
        result = await self._session.execute(
            select(TicketModel, EventModel, TicketTypeModel, OrderModel)
            .join(EventModel, TicketModel.event_id == EventModel.id)
            .join(TicketTypeModel, TicketModel.ticket_type_id == TicketTypeModel.id)
            .join(OrderModel, TicketModel.order_id == OrderModel.id)
            .where(TicketModel.owner_id == user_id)
            .order_by(TicketModel.id.desc())
        )
        rows = result.all()
        return [
            {
                "id": str(t.id),
                "order_id": str(t.order_id),
                "event_id": str(t.event_id),
                "event_name": ev.name,
                "event_date": ev.event_date.isoformat(),
                "event_time": ev.event_time.isoformat(),
                "city": ev.city,
                "address": ev.address,
                "holder_name": t.holder_name,
                "ticket_type": tt.name,
                "price": float(tt.price),
                "qr_token": t.qr_token,
                "ticket_code": t.ticket_code,
                "is_used": t.is_used,
                "main_image_url": ev.main_image_url,
                "pdf_url": f"/tickets/orders/{t.order_id}/pdf",
            }
            for t, ev, tt, _o in rows
        ]

    async def list_seller_sales(self, seller_id: UUID) -> list[dict]:
        result = await self._session.execute(
            select(OrderModel, EventModel)
            .join(EventModel, OrderModel.event_id == EventModel.id)
            .where(OrderModel.seller_id == seller_id)
            .order_by(OrderModel.created_at.desc())
        )
        out = []
        for order, ev in result.all():
            tix = await self._session.execute(
                select(TicketModel).where(TicketModel.order_id == order.id)
            )
            tickets = tix.scalars().all()
            out.append(
                {
                    "order_id": str(order.id),
                    "event_name": ev.name,
                    "total": float(order.total_amount),
                    "quantity": len(tickets),
                    "created_at": order.created_at.isoformat() if order.created_at else None,
                    "pdf_url": f"/tickets/orders/{order.id}/pdf",
                    "holders": [t.holder_name for t in tickets],
                }
            )
        return out
