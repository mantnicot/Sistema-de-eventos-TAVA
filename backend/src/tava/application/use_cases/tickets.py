from decimal import Decimal
import secrets
import string
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from tava.application.use_cases.seating import SeatingUseCase, seating_enabled
from tava.config import get_settings
from tava.domain.enums import PaymentProvider, PaymentStatus
from tava.domain.event_timing import tickets_purchase_allowed
from tava.infrastructure.persistence.models import EventModel, OrderModel, TicketModel, TicketTypeModel, UserModel
from tava.infrastructure.persistence.repositories.sqlalchemy_user_repository import SQLAlchemyUserRepository
from tava.infrastructure.security.ticket_codes import assign_unique_ticket_code, backfill_missing_ticket_codes
from tava.infrastructure.security.ticket_tokens import generate_qr_token, generate_security_hash
from tava.infrastructure.services.email import last_email_failure, send_tickets_confirmation_email
from tava.infrastructure.services.ticket_pdf import build_tickets_pdf
from tava.infrastructure.services.wompi import (
    amount_in_cents,
    build_checkout_url,
    wompi_configured,
)

settings = get_settings()
CLAIM_CODE_ALPHABET = string.ascii_uppercase + string.digits


def _normalize_claim_code(code: str) -> str:
    return code.strip().upper().replace(" ", "").replace("-", "")


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

    async def _assign_unique_claim_code(self) -> str:
        for _ in range(30):
            raw = "".join(secrets.choice(CLAIM_CODE_ALPHABET) for _ in range(10))
            code = f"TAVA{raw}"
            exists = await self._session.execute(
                select(OrderModel.id).where(OrderModel.claim_code == code)
            )
            if not exists.scalar_one_or_none():
                return code
        raise ValueError("No se pudo generar un cÃ³digo de reclamo Ãºnico")

    async def backfill_missing_claim_codes(self) -> int:
        result = await self._session.execute(
            select(OrderModel).where(
                OrderModel.payment_status == PaymentStatus.PAID,
                OrderModel.claim_code.is_(None),
            )
        )
        orders = result.scalars().all()
        for order in orders:
            order.claim_code = await self._assign_unique_claim_code()
        if orders:
            await self._session.flush()
        return len(orders)

    def _assert_tickets_on_sale(self, event: EventModel) -> None:
        details = event.theatrical_details if isinstance(event.theatrical_details, dict) else None
        if not tickets_purchase_allowed(
            event_date=event.event_date,
            event_time=event.event_time,
            theatrical_details=details,
            status=event.status,
        ):
            raise ValueError(
                "Te perdiste este evento, pero tenemos otros para ti. "
                "Revisa la cartelera de funciones disponibles."
            )

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
        issue_tickets: bool = True,
        payment_provider: PaymentProvider | None = None,
        payment_reference: str | None = None,
        seat_ids: list[UUID] | None = None,
    ) -> tuple[OrderModel, list[TicketModel], EventModel, TicketTypeModel]:
        if quantity < 1 or quantity > 20:
            raise ValueError("Cantidad inválida (1-20)")
        event = await self._load_event(event_id)
        if seating_enabled(event):
            if not seat_ids or len(seat_ids) != quantity:
                raise ValueError("Debes seleccionar una silla por cada boleta")
        elif seat_ids:
            raise ValueError("Este evento no tiene silletería numerada")
        ticket_type = await self._load_ticket_type(ticket_type_id, event_id)
        if ticket_type.quantity_available < quantity:
            raise ValueError("Cantidad no disponible")

        names = self._normalize_holder_names(quantity, holder_names, buyer_display_name)
        total = ticket_type.price * quantity
        provider = payment_provider or (PaymentProvider.MANUAL if seller_id else PaymentProvider.MANUAL)
        order = OrderModel(
            buyer_id=buyer_id,
            seller_id=seller_id,
            event_id=event_id,
            total_amount=total,
            payment_status=PaymentStatus.PAID if mark_paid else PaymentStatus.PENDING,
            payment_provider=provider,
            payment_reference=payment_reference,
            claim_code=await self._assign_unique_claim_code(),
            pending_payload=(
                None
                if issue_tickets
                else {
                    "ticket_type_id": str(ticket_type_id),
                    "quantity": quantity,
                    "holder_names": names,
                    "seat_ids": [str(s) for s in seat_ids] if seat_ids else None,
                }
            ),
            legal_accepted=True,
        )
        self._session.add(order)
        await self._session.flush()

        ticket_type.quantity_available -= quantity

        created: list[TicketModel] = []
        if issue_tickets:
            created = await self._issue_tickets_for_order(
                order=order,
                event=event,
                ticket_type=ticket_type,
                buyer_id=buyer_id,
                names=names,
            )
            if seat_ids:
                await SeatingUseCase(self._session).assign_seats_to_tickets(
                    event.id, seat_ids, created, ticket_type.id
                )

        await self._session.flush()
        return order, created, event, ticket_type

    async def _issue_tickets_for_order(
        self,
        *,
        order: OrderModel,
        event: EventModel,
        ticket_type: TicketTypeModel,
        buyer_id: UUID,
        names: list[str],
    ) -> list[TicketModel]:
        created: list[TicketModel] = []
        used_codes: set[str] = set()
        for name in names:
            ticket_id = uuid4()
            qr = generate_qr_token()
            ticket_code = await assign_unique_ticket_code(self._session)
            while ticket_code in used_codes:
                ticket_code = await assign_unique_ticket_code(self._session)
            used_codes.add(ticket_code)
            ticket = TicketModel(
                id=ticket_id,
                order_id=order.id,
                ticket_type_id=ticket_type.id,
                owner_id=buyer_id,
                event_id=event.id,
                holder_name=name,
                qr_token=qr,
                ticket_code=ticket_code,
                security_hash="",
            )
            ticket.security_hash = generate_security_hash(
                ticket_id, ticket.event_id, ticket.qr_token, settings.jwt_secret_key
            )
            self._session.add(ticket)
            created.append(ticket)
        await self._session.flush()
        return created

    async def _restore_stock(self, order: OrderModel) -> None:
        payload = order.pending_payload or {}
        ticket_type_id = payload.get("ticket_type_id")
        quantity = payload.get("quantity")
        if not ticket_type_id or not quantity:
            return
        result = await self._session.execute(
            select(TicketTypeModel).where(TicketTypeModel.id == UUID(str(ticket_type_id)))
        )
        tt = result.scalar_one_or_none()
        if tt:
            tt.quantity_available += int(quantity)

    async def fulfill_paid_order(
        self, order: OrderModel, *, wompi_transaction_id: str | None = None
    ) -> tuple[list[TicketModel], EventModel, TicketTypeModel]:
        if order.payment_status == PaymentStatus.PAID:
            result = await self._session.execute(
                select(OrderModel)
                .where(OrderModel.id == order.id)
                .options(selectinload(OrderModel.tickets))
            )
            order = result.scalar_one()
            if order.tickets:
                if not order.claim_code:
                    order.claim_code = await self._assign_unique_claim_code()
                    await self._session.flush()
                event = await self._load_event(order.event_id)
                tt = await self._load_ticket_type(order.tickets[0].ticket_type_id, order.event_id)
                return order.tickets, event, tt

        payload = order.pending_payload
        if not payload:
            raise ValueError("Orden sin datos pendientes para emitir boletas")

        ticket_type_id = UUID(str(payload["ticket_type_id"]))
        quantity = int(payload["quantity"])
        names = list(payload.get("holder_names") or [])
        seat_ids_raw = payload.get("seat_ids")
        seat_ids = [UUID(str(s)) for s in seat_ids_raw] if seat_ids_raw else None
        event = await self._load_event(order.event_id)
        ticket_type = await self._load_ticket_type(ticket_type_id, order.event_id)

        order.payment_status = PaymentStatus.PAID
        order.payment_provider = PaymentProvider.WOMPI
        if not order.claim_code:
            order.claim_code = await self._assign_unique_claim_code()
        if wompi_transaction_id:
            order.wompi_transaction_id = wompi_transaction_id
        order.pending_payload = None

        tickets = await self._issue_tickets_for_order(
            order=order,
            event=event,
            ticket_type=ticket_type,
            buyer_id=order.buyer_id,
            names=names[:quantity] if names else [""] * quantity,
        )
        if seat_ids:
            await SeatingUseCase(self._session).assign_seats_to_tickets(
                event.id, seat_ids, tickets, ticket_type.id
            )
        await self._session.flush()
        return tickets, event, ticket_type

    async def reject_pending_order(self, order: OrderModel) -> None:
        if order.payment_status != PaymentStatus.PENDING:
            return
        order.payment_status = PaymentStatus.REJECTED
        await self._restore_stock(order)
        order.pending_payload = None
        await self._session.flush()

    async def create_wompi_checkout(
        self,
        *,
        user_id: UUID,
        user_name: str,
        user_email: str,
        event_id: UUID,
        ticket_type_id: UUID,
        quantity: int,
        holder_names: list[str] | None,
        seat_ids: list[UUID] | None = None,
    ) -> dict:
        payment_reference = f"TAVA-{uuid4().hex[:12].upper()}"
        order, _, event, tt = await self.create_order(
            event_id=event_id,
            ticket_type_id=ticket_type_id,
            quantity=quantity,
            buyer_id=user_id,
            seller_id=None,
            holder_names=holder_names,
            buyer_display_name=user_name,
            mark_paid=False,
            issue_tickets=False,
            payment_provider=PaymentProvider.WOMPI,
            payment_reference=payment_reference,
            seat_ids=seat_ids,
        )
        redirect_url = f"{settings.frontend_url.rstrip('/')}/compra/resultado?order_id={order.id}"
        cents = amount_in_cents(order.total_amount)
        checkout_url = build_checkout_url(
            reference=payment_reference,
            amount_cents=cents,
            redirect_url=redirect_url,
            customer_email=user_email,
            customer_name=user_name,
        )
        return {
            "payment_required": True,
            "order_id": str(order.id),
            "payment_reference": payment_reference,
            "checkout_url": checkout_url,
            "total": float(order.total_amount),
            "amount_in_cents": cents,
            "event_name": event.name,
            "ticket_type": tt.name,
            "payment_status": order.payment_status.value,
            "message": "Redirigiendo a Wompi para completar el pago.",
        }

    async def get_order_status(self, order_id: UUID, user_id: UUID, is_admin: bool) -> dict:
        result = await self._session.execute(
            select(OrderModel)
            .where(OrderModel.id == order_id)
            .options(selectinload(OrderModel.tickets))
        )
        order = result.scalar_one_or_none()
        if not order:
            raise ValueError("Orden no encontrada")
        if not is_admin and order.buyer_id != user_id:
            raise ValueError("No autorizado")
        event = await self._load_event(order.event_id)
        ticket_type_name = None
        if order.tickets:
            tt = await self._load_ticket_type(order.tickets[0].ticket_type_id, order.event_id)
            ticket_type_name = tt.name
        elif order.pending_payload:
            tt = await self._load_ticket_type(
                UUID(str(order.pending_payload["ticket_type_id"])), order.event_id
            )
            ticket_type_name = tt.name
        return {
            "order_id": str(order.id),
            "payment_status": order.payment_status.value,
            "payment_reference": order.payment_reference,
            "wompi_transaction_id": order.wompi_transaction_id,
            "total": float(order.total_amount),
            "event_name": event.name,
            "ticket_type": ticket_type_name,
            "tickets_ready": order.payment_status == PaymentStatus.PAID and bool(order.tickets),
            "pdf_url": f"/tickets/orders/{order.id}/pdf" if order.tickets else None,
            "claim_code": order.claim_code if order.payment_status == PaymentStatus.PAID else None,
        }

    async def handle_wompi_transaction_update(
        self, reference: str, status: str, transaction_id: str | None
    ) -> dict:
        result = await self._session.execute(
            select(OrderModel)
            .where(OrderModel.payment_reference == reference)
            .options(selectinload(OrderModel.tickets))
        )
        order = result.scalar_one_or_none()
        if not order:
            return {"handled": False, "reason": "order_not_found"}

        if status == "APPROVED":
            already_fulfilled = order.payment_status == PaymentStatus.PAID and bool(order.tickets)
            tickets, event, tt = await self.fulfill_paid_order(
                order, wompi_transaction_id=transaction_id
            )
            if not already_fulfilled:
                return {
                    "handled": True,
                    "payment_status": "pagado",
                    "order_id": str(order.id),
                    "email_pending": True,
                }
            return {"handled": True, "payment_status": "pagado", "order_id": str(order.id)}

        if status in ("DECLINED", "VOIDED", "ERROR"):
            await self.reject_pending_order(order)
            return {"handled": True, "payment_status": "rechazado", "order_id": str(order.id)}

        return {"handled": True, "payment_status": order.payment_status.value, "order_id": str(order.id)}

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
            claim_code=order.claim_code,
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
                claim_code=order.claim_code,
            )

    async def _send_pdf_to_external_buyer(
        self,
        *,
        order: OrderModel,
        tickets: list[TicketModel],
        event: EventModel,
        ticket_type: TicketTypeModel,
        buyer_email: str,
        buyer_name: str,
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
            tickets=[(t.qr_token, t.holder_name or buyer_name, t.ticket_code or "") for t in tickets],
        )
        ok = await send_tickets_confirmation_email(
            buyer_email,
            buyer_name,
            event.name,
            len(tickets),
            pdf,
            is_seller_copy=False,
            event_date=event.event_date.isoformat(),
            event_time=event.event_time.strftime("%H:%M"),
            claim_code=order.claim_code,
        )
        if not ok:
            raise ValueError(last_email_failure() or "No se pudo enviar el correo al comprador")

    async def send_order_confirmation_email(self, order_id: UUID) -> bool:
        result = await self._session.execute(
            select(OrderModel)
            .where(OrderModel.id == order_id)
            .options(selectinload(OrderModel.tickets))
        )
        order = result.scalar_one_or_none()
        if not order or not order.tickets:
            return False

        event = await self._load_event(order.event_id)
        tt = await self._load_ticket_type(order.tickets[0].ticket_type_id, order.event_id)

        buyer_result = await self._session.execute(
            select(UserModel).where(UserModel.id == order.buyer_id)
        )
        buyer = buyer_result.scalar_one_or_none()
        if not buyer:
            return False

        seller = None
        if order.seller_id:
            seller_result = await self._session.execute(
                select(UserModel).where(UserModel.id == order.seller_id)
            )
            seller = seller_result.scalar_one_or_none()

        await self._send_pdf_emails(order, order.tickets, event, tt, buyer, seller)
        return True

    async def claim_order_by_code(self, user_id: UUID, code: str) -> dict:
        normalized = _normalize_claim_code(code)
        result = await self._session.execute(
            select(OrderModel)
            .where(OrderModel.claim_code == normalized)
            .options(selectinload(OrderModel.tickets))
        )
        order = result.scalar_one_or_none()
        if not order:
            raise ValueError("CÃ³digo no encontrado")
        if order.payment_status != PaymentStatus.PAID:
            raise ValueError("La orden todavÃ­a no estÃ¡ pagada")
        if not order.tickets:
            raise ValueError("La orden no tiene boletas disponibles")

        order.buyer_id = user_id
        for ticket in order.tickets:
            ticket.owner_id = user_id
        await self._session.flush()
        return {
            "message": "Boletas reclamadas. Ya puedes verlas en tu perfil.",
            "order_id": str(order.id),
            "pdf_url": f"/tickets/orders/{order.id}/pdf",
            "tickets_count": len(order.tickets),
        }

    async def issue_claim_order_as_admin(
        self,
        *,
        admin_id: UUID,
        buyer_name: str,
        buyer_email: str,
        event_id: UUID,
        ticket_type_id: UUID,
        quantity: int,
        holder_names: list[str] | None,
    ) -> dict:
        event = await self._load_event(event_id)
        if seating_enabled(event):
            raise ValueError("Este evento tiene silleterÃ­a numerada; emite estas boletas desde el flujo con sillas.")
        self._assert_tickets_on_sale(event)

        order, tickets, event, tt = await self.create_order(
            event_id=event_id,
            ticket_type_id=ticket_type_id,
            quantity=quantity,
            buyer_id=admin_id,
            seller_id=admin_id,
            holder_names=holder_names,
            buyer_display_name=buyer_name,
            mark_paid=True,
            issue_tickets=True,
            payment_provider=PaymentProvider.MANUAL,
        )
        await self._send_pdf_to_external_buyer(
            order=order,
            tickets=tickets,
            event=event,
            ticket_type=tt,
            buyer_email=buyer_email,
            buyer_name=buyer_name,
        )
        return {
            "message": "Boletas generadas y correo enviado al comprador.",
            "order_id": str(order.id),
            "claim_code": order.claim_code,
            "pdf_url": f"/tickets/orders/{order.id}/pdf",
            "event_name": event.name,
            "event_date": event.event_date.isoformat(),
            "event_time": event.event_time.isoformat(),
            "ticket_type": tt.name,
            "quantity": len(tickets),
            "total": float(order.total_amount),
            "buyer_name": buyer_name,
            "buyer_email": buyer_email,
        }

    async def purchase_for_user(
        self,
        user_id: UUID,
        user_name: str,
        user_email: str,
        event_id: UUID,
        ticket_type_id: UUID,
        quantity: int,
        holder_names: list[str] | None,
        seat_ids: list[UUID] | None = None,
    ) -> dict:
        event = await self._load_event(event_id)
        self._assert_tickets_on_sale(event)
        tt = await self._load_ticket_type(ticket_type_id, event_id)
        total = tt.price * quantity

        if total <= 0:
            order, tickets, event, tt = await self.create_order(
                event_id=event_id,
                ticket_type_id=ticket_type_id,
                quantity=quantity,
                buyer_id=user_id,
                seller_id=None,
                holder_names=holder_names,
                buyer_display_name=user_name,
                mark_paid=True,
                issue_tickets=True,
                payment_provider=PaymentProvider.MANUAL,
                seat_ids=seat_ids,
            )
            buyer_model = await self._users.get_model_by_email(user_email)
            response = self._order_response(order, tickets, event, tt)
            response["payment_required"] = False
            response["email_pending"] = bool(buyer_model)
            return response

        if wompi_configured():
            return await self.create_wompi_checkout(
                user_id=user_id,
                user_name=user_name,
                user_email=user_email,
                event_id=event_id,
                ticket_type_id=ticket_type_id,
                quantity=quantity,
                holder_names=holder_names,
                seat_ids=seat_ids,
            )

        order, tickets, event, tt = await self.create_order(
            event_id=event_id,
            ticket_type_id=ticket_type_id,
            quantity=quantity,
            buyer_id=user_id,
            seller_id=None,
            holder_names=holder_names,
            buyer_display_name=user_name,
            mark_paid=True,
            issue_tickets=True,
            payment_provider=PaymentProvider.MANUAL,
            seat_ids=seat_ids,
        )
        buyer_model = await self._users.get_model_by_email(user_email)
        response = self._order_response(order, tickets, event, tt)
        response["payment_required"] = False
        response["email_pending"] = bool(buyer_model)
        return response

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
        event = await self._load_event(event_id)
        self._assert_tickets_on_sale(event)
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
        response = self._order_response(order, tickets, event, tt)
        response["email_pending"] = True
        return response

    def _order_response(
        self, order: OrderModel, tickets: list[TicketModel], event: EventModel, tt: TicketTypeModel
    ) -> dict:
        return {
            "order_id": str(order.id),
            "total": float(order.total_amount),
            "payment_status": order.payment_status.value,
            "payment_required": False,
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
            "claim_code": order.claim_code,
            "message": "Boletas generadas. Ya puedes descargarlas; tambien enviaremos el PDF a tu correo.",
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

    async def get_ticket_pdf_bytes(self, ticket_id: UUID, user_id: UUID, is_admin: bool) -> bytes:
        result = await self._session.execute(
            select(TicketModel, EventModel, TicketTypeModel, OrderModel)
            .join(EventModel, TicketModel.event_id == EventModel.id)
            .join(TicketTypeModel, TicketModel.ticket_type_id == TicketTypeModel.id)
            .join(OrderModel, TicketModel.order_id == OrderModel.id)
            .where(TicketModel.id == ticket_id)
        )
        row = result.one_or_none()
        if not row:
            raise ValueError("Boleta no encontrada")
        ticket, event, tt, order = row
        if not is_admin and ticket.owner_id != user_id and order.buyer_id != user_id:
            raise ValueError("No autorizado")
        if ticket.is_cancelled:
            raise ValueError("Boleta cancelada")
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
            tickets=[(ticket.qr_token, ticket.holder_name or "", ticket.ticket_code or "")],
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
                "is_cancelled": t.is_cancelled,
                "main_image_url": ev.main_image_url,
                "pdf_url": f"/tickets/{t.id}/pdf",
            }
            for t, ev, tt, _o in rows
        ]

    async def list_seller_sales(self, seller_id: UUID) -> list[dict]:
        result = await self._session.execute(
            select(TicketModel, EventModel, TicketTypeModel, OrderModel)
            .join(EventModel, TicketModel.event_id == EventModel.id)
            .join(TicketTypeModel, TicketModel.ticket_type_id == TicketTypeModel.id)
            .join(OrderModel, TicketModel.order_id == OrderModel.id)
            .where(OrderModel.seller_id == seller_id)
            .order_by(OrderModel.created_at.desc(), TicketModel.id.desc())
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
                "holder_name": t.holder_name,
                "ticket_type": tt.name,
                "price": float(tt.price),
                "ticket_code": t.ticket_code,
                "is_used": t.is_used,
                "is_cancelled": t.is_cancelled,
                "claim_code": order.claim_code,
                "created_at": order.created_at.isoformat() if order.created_at else None,
                "pdf_url": f"/tickets/{t.id}/pdf",
                "order_pdf_url": f"/tickets/orders/{order.id}/pdf",
            }
            for t, ev, tt, order in rows
        ]
