from abc import ABC, abstractmethod
from uuid import UUID

from tava.domain.entities.event import Event
from tava.domain.enums import EventStatus


class EventRepository(ABC):
    @abstractmethod
    async def get_by_id(self, event_id: UUID) -> Event | None: ...

    @abstractmethod
    async def list_public(
        self,
        search: str | None = None,
        category: str | None = None,
        status: EventStatus | None = EventStatus.PUBLISHED,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Event]: ...

    @abstractmethod
    async def create(self, **kwargs) -> Event: ...

    @abstractmethod
    async def update(self, event_id: UUID, **kwargs) -> Event | None: ...
