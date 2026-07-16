"""Silletería numerada por evento."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from tava.domain.enums import SeatStatus
from tava.infrastructure.persistence.models import EventModel, EventSeatModel, TicketModel


def _row_labels(count: int, custom: list[str] | None) -> list[str]:
    if custom and len(custom) >= count:
        return custom[:count]
    labels: list[str] = []
    for i in range(count):
        if i < 26:
            labels.append(chr(65 + i))
        else:
            labels.append(str(i + 1))
    return labels


def _col_labels(count: int, custom: list[str] | None) -> list[str]:
    if custom and len(custom) >= count:
        return custom[:count]
    return [str(i + 1) for i in range(count)]


def _seat_key(block_id: str, row: str, col: str) -> str:
    return f"{block_id}|{row}|{col}"


def count_layout_seats(blocks: list[dict]) -> int:
    total = 0
    for block in blocks:
        rows = int(block.get("rows") or 1)
        cols = int(block.get("cols") or 1)
        total += rows * cols
    return total


def resolve_ticket_type_id(
    block: dict, row: str, col: str, seat_ticket_types: dict[str, str] | None
) -> UUID | None:
    block_id = str(block.get("id") or "main")
    key = _seat_key(block_id, row, col)
    raw = (seat_ticket_types or {}).get(key)
    if raw is None:
        raw = block.get("ticket_type_id")
    if not raw:
        return None
    try:
        return UUID(str(raw))
    except (TypeError, ValueError):
        return None


def seating_config_from_event(event: EventModel) -> dict | None:
    if not event.theatrical_details or not isinstance(event.theatrical_details, dict):
        return None
    seating = event.theatrical_details.get("seating")
    if not isinstance(seating, dict):
        return None
    return seating


def seating_enabled(event: EventModel) -> bool:
    return False


class SeatingUseCase:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_map(self, event_id: UUID) -> dict:
        event = await self._load_event(event_id)
        cfg = seating_config_from_event(event)
        if not cfg or not seating_enabled(event):
            return {"enabled": False, "seats": [], "config": None}

        result = await self._session.execute(
            select(EventSeatModel).where(EventSeatModel.event_id == event_id)
        )
        seats = result.scalars().all()
        return {
            "enabled": True,
            "config": cfg,
            "seats": [
                {
                    "id": str(s.id),
                    "block_id": s.block_id,
                    "row": s.row_label,
                    "col": s.col_label,
                    "label": s.label,
                    "status": s.status.value,
                    "ticket_type_id": str(s.ticket_type_id) if s.ticket_type_id else None,
                }
                for s in seats
            ],
        }

    async def sync_layout(self, event_id: UUID, seating: dict) -> dict:
        event = await self._load_event(event_id)
        blocks = seating.get("blocks") or []
        seat_ticket_types = seating.get("seat_ticket_types") or {}

        if seating.get("enabled"):
            total = count_layout_seats(blocks)
            if event.capacity and event.capacity > 0 and total > event.capacity:
                raise ValueError(
                    f"El mapa tiene {total} sillas pero el aforo del evento es {event.capacity}. "
                    "Reduce filas, columnas o bloques."
                )

        details = dict(event.theatrical_details or {})
        details["seating"] = seating
        event.theatrical_details = details

        if not seating.get("enabled"):
            await self._session.execute(
                delete(EventSeatModel).where(
                    EventSeatModel.event_id == event_id,
                    EventSeatModel.status != SeatStatus.SOLD,
                )
            )
            await self._session.flush()
            return {"enabled": False, "seats_created": 0}

        sold_result = await self._session.execute(
            select(EventSeatModel).where(
                EventSeatModel.event_id == event_id,
                EventSeatModel.status == SeatStatus.SOLD,
            )
        )
        sold_keys = {(s.block_id, s.row_label, s.col_label) for s in sold_result.scalars().all()}

        await self._session.execute(
            delete(EventSeatModel).where(
                EventSeatModel.event_id == event_id,
                EventSeatModel.status != SeatStatus.SOLD,
            )
        )

        created = 0
        for block in blocks:
            block_id = str(block.get("id") or "main")
            block_name = str(block.get("name") or block_id)
            rows = int(block.get("rows") or 1)
            cols = int(block.get("cols") or 1)
            row_labels = _row_labels(rows, block.get("row_labels"))
            col_labels = _col_labels(cols, block.get("col_labels"))
            for row in row_labels:
                for col in col_labels:
                    key = (block_id, row, col)
                    if key in sold_keys:
                        continue
                    label = f"{block_name} · Fila {row} · Asiento {col}"
                    ticket_type_id = resolve_ticket_type_id(block, row, col, seat_ticket_types)
                    self._session.add(
                        EventSeatModel(
                            event_id=event_id,
                            block_id=block_id,
                            row_label=row,
                            col_label=col,
                            label=label,
                            status=SeatStatus.AVAILABLE,
                            ticket_type_id=ticket_type_id,
                        )
                    )
                    created += 1

        await self._session.flush()
        return {"enabled": True, "seats_created": created}

    async def assign_seats_to_tickets(
        self,
        event_id: UUID,
        seat_ids: list[UUID],
        tickets: list[TicketModel],
        ticket_type_id: UUID,
    ) -> None:
        if len(seat_ids) != len(tickets):
            raise ValueError("La cantidad de sillas debe coincidir con las boletas")
        result = await self._session.execute(
            select(EventSeatModel).where(
                EventSeatModel.event_id == event_id,
                EventSeatModel.id.in_(seat_ids),
            )
        )
        seats = {s.id: s for s in result.scalars().all()}
        if len(seats) != len(seat_ids):
            raise ValueError("Una o más sillas no existen")
        for seat_id, ticket in zip(seat_ids, tickets, strict=True):
            seat = seats.get(seat_id)
            if not seat:
                raise ValueError("Silla no encontrada")
            if seat.status == SeatStatus.SOLD:
                raise ValueError(f"La silla {seat.label} ya está ocupada")
            if seat.status == SeatStatus.BLOCKED:
                raise ValueError(f"La silla {seat.label} no está disponible")
            if seat.ticket_type_id and seat.ticket_type_id != ticket_type_id:
                raise ValueError(
                    f"La silla {seat.label} no corresponde al tipo de boleta seleccionado"
                )
            seat.status = SeatStatus.SOLD
            ticket.event_seat_id = seat.id

    async def _load_event(self, event_id: UUID) -> EventModel:
        result = await self._session.execute(select(EventModel).where(EventModel.id == event_id))
        event = result.scalar_one_or_none()
        if not event:
            raise ValueError("Evento no encontrado")
        return event
