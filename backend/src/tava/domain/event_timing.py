"""Estado temporal de eventos (próximo, en curso, finalizado)."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from tava.domain.enums import EventStatus

BOGOTA_TZ = ZoneInfo("America/Bogota")
DEFAULT_DURATION_MINUTES = 120


def event_start_datetime(event_date: date, event_time: time) -> datetime:
    return datetime.combine(event_date, event_time, tzinfo=BOGOTA_TZ)


def event_duration_minutes(theatrical_details: dict | None) -> int:
    if theatrical_details and theatrical_details.get("duration_minutes"):
        try:
            return max(30, int(theatrical_details["duration_minutes"]))
        except (TypeError, ValueError):
            pass
    return DEFAULT_DURATION_MINUTES


def event_end_datetime(
    event_date: date, event_time: time, theatrical_details: dict | None
) -> datetime:
    start = event_start_datetime(event_date, event_time)
    return start + timedelta(minutes=event_duration_minutes(theatrical_details))


def event_phase(
    *,
    event_date: date,
    event_time: time,
    theatrical_details: dict | None,
    status: EventStatus,
) -> str:
    """upcoming | live | finished"""
    if status in (EventStatus.FINISHED, EventStatus.CANCELLED):
        return "finished"
    now = datetime.now(BOGOTA_TZ)
    start = event_start_datetime(event_date, event_time)
    end = event_end_datetime(event_date, event_time, theatrical_details)
    if now >= end:
        return "finished"
    if status == EventStatus.IN_PROGRESS or now >= start:
        return "live"
    return "upcoming"


def door_validation_state(
    *,
    event_date: date,
    event_time: time,
    theatrical_details: dict | None,
    status: EventStatus,
) -> str:
    """open | before_day | after_day | closed.

    La puerta abre el día de la función, desde las 00:00 (Bogotá), y sigue
    abierta hasta que termina el día o la función si se pasa de medianoche.
    """
    if status in (EventStatus.CANCELLED, EventStatus.DRAFT, EventStatus.FINISHED):
        return "closed"
    if status not in (
        EventStatus.PUBLISHED,
        EventStatus.IN_PROGRESS,
        EventStatus.SOLD_OUT,
        EventStatus.SCHEDULED,
    ):
        return "closed"
    now = datetime.now(BOGOTA_TZ)
    day_start = datetime.combine(event_date, time.min, tzinfo=BOGOTA_TZ)
    show_end = event_end_datetime(event_date, event_time, theatrical_details)
    day_end = day_start + timedelta(days=1)
    window_end = show_end if show_end > day_end else day_end
    if now < day_start:
        return "before_day"
    if now >= window_end:
        return "after_day"
    return "open"


def tickets_purchase_allowed(
    *,
    event_date: date,
    event_time: time,
    theatrical_details: dict | None,
    status: EventStatus,
) -> bool:
    if status in (EventStatus.CANCELLED, EventStatus.FINISHED, EventStatus.DRAFT):
        return False
    return event_phase(
        event_date=event_date,
        event_time=event_time,
        theatrical_details=theatrical_details,
        status=status,
    ) == "upcoming"
