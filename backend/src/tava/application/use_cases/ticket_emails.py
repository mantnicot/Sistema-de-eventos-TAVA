import logging
from uuid import UUID

from tava.application.use_cases.tickets import TicketUseCase
from tava.infrastructure.persistence.database import AsyncSessionLocal

logger = logging.getLogger("tava.ticket_emails")


async def send_order_confirmation_email_background(order_id: UUID) -> None:
    async with AsyncSessionLocal() as session:
        try:
            sent = await TicketUseCase(session).send_order_confirmation_email(order_id)
            if sent:
                logger.info("Correo de boletas enviado para order=%s", order_id)
            else:
                logger.warning("No habia boletas listas para enviar por correo order=%s", order_id)
        except Exception:
            logger.exception("No se pudo enviar el correo de boletas order=%s", order_id)
