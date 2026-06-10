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
