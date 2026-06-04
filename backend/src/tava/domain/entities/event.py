from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from uuid import UUID

from tava.domain.enums import EventStatus


@dataclass
class Event:
    id: UUID
    name: str
    description: str
    event_date: date
    event_time: time
    city: str
    address: str
    category: str
    status: EventStatus
    capacity: int
    organizer_id: UUID
    created_at: datetime
    main_image_url: str | None = None
    trailer_url: str | None = None
