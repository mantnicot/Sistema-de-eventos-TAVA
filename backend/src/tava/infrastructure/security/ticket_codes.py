import secrets

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tava.infrastructure.persistence.models import TicketModel


def generate_ticket_code() -> str:
    """Código numérico de 8 dígitos, legible en taquilla."""
    return f"{secrets.randbelow(100_000_000):08d}"


async def assign_unique_ticket_code(session: AsyncSession) -> str:
    for _ in range(30):
        code = generate_ticket_code()
        exists = await session.execute(
            select(TicketModel.id).where(TicketModel.ticket_code == code)
        )
        if not exists.scalar_one_or_none():
            return code
    raise ValueError("No se pudo generar un código único para la boleta")


async def backfill_missing_ticket_codes(session: AsyncSession) -> int:
    result = await session.execute(
        select(TicketModel).where(TicketModel.ticket_code.is_(None))
    )
    tickets = result.scalars().all()
    count = 0
    for ticket in tickets:
        ticket.ticket_code = await assign_unique_ticket_code(session)
        count += 1
    if count:
        await session.flush()
    return count
