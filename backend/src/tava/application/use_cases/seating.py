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


def seating_config_from_event(event: EventModel) -> dict | None:
    if not event.theatrical_details or not isinstance(event.theatrical_details, dict):
        return None
    seating = event.theatrical_details.get("seating")
    if not isinstance(seating, dict):
        return None
    return seating


def seating_enabled(event: EventModel) -> bool:
    cfg = seating_config_from_event(event)
    return bool(cfg and cfg.get("enabled"))


class SeatingUseCase:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_map(self, event_id: UUID) -> dict:
        event = await self._load_event(event_id)
        cfg = seating_config_from_event(event)
        if not cfg or not cfg.get("enabled"):
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
                }
                for s in seats
            ],
        }

    async def sync_layout(self, event_id: UUID, seating: dict) -> dict:
        event = await self._load_event(event_id)
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
        blocks = seating.get("blocks") or []
        for block in blocks:
            block_id = str(block.get("id") or "main")
            block_name = str(block.get("name") or block_id)
            rows = int(block.get("rows") or 1)
            cols = int(block.get("cols") or 1)
            row_labels = _row_labels(rows, block.get("row_labels"))
            col_labels = _col_labels(cols, block.get("col_labels"))
            for ri, row in enumerate(row_labels):
                for ci, col in enumerate(col_labels):
                    key = (block_id, row, col)
                    if key in sold_keys:
                        continue
                    label = f"{block_name} · Fila {row} · Asiento {col}"
                    self._session.add(
                        EventSeatModel(
                            event_id=event_id,
                            block_id=block_id,
                            row_label=row,
                            col_label=col,
                            label=label,
                            status=SeatStatus.AVAILABLE,
                        )
                    )
                    created += 1

        await self._session.flush()
        return {"enabled": True, "seats_created": created}

    async def assign_seats_to_tickets(
        self, event_id: UUID, seat_ids: list[UUID], tickets: list[TicketModel]
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
            seat.status = SeatStatus.SOLD
            ticket.event_seat_id = seat.id

    async def _load_event(self, event_id: UUID) -> EventModel:
        result = await self._session.execute(select(EventModel).where(EventModel.id == event_id))
        event = result.scalar_one_or_none()
        if not event:
            raise ValueError("Evento no encontrado")
        return event
