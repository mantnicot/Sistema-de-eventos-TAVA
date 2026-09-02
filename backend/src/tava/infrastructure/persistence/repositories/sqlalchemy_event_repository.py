from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from tava.domain.entities.event import Event
from tava.domain.enums import EventReviewStatus, EventStatus
from tava.domain.repositories.event_repository import EventRepository
from tava.infrastructure.persistence.models import EventModel


def _to_entity(m: EventModel) -> Event:
    return Event(
        id=m.id,
        name=m.name,
        description=m.description,
        event_date=m.event_date,
        event_time=m.event_time,
        city=m.city,
        address=m.address,
        category=m.category,
        status=m.status,
        capacity=m.capacity,
        organizer_id=m.organizer_id,
        created_at=m.created_at,
        main_image_url=m.main_image_url,
        trailer_url=m.trailer_url,
        theatrical_details=m.theatrical_details,
    )


class SQLAlchemyEventRepository(EventRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, event_id: UUID) -> Event | None:
        result = await self._session.execute(select(EventModel).where(EventModel.id == event_id))
        row = result.scalar_one_or_none()
        return _to_entity(row) if row else None

    async def list_public(
        self,
        search: str | None = None,
        category: str | None = None,
        status: EventStatus | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Event]:
        q = (
            select(EventModel)
            .where(
                EventModel.review_status == EventReviewStatus.APPROVED,
                EventModel.cartelera_visible.is_(True),
                EventModel.status.notin_([EventStatus.DRAFT, EventStatus.CANCELLED]),
            )
            .order_by(EventModel.event_date.asc())
            .limit(limit)
            .offset(offset)
        )
        if status:
            q = q.where(EventModel.status == status)
        if category:
            q = q.where(EventModel.category.ilike(f"%{category}%"))
        if search:
            pattern = f"%{search}%"
            q = q.where(or_(EventModel.name.ilike(pattern), EventModel.description.ilike(pattern)))
        result = await self._session.execute(q)
        return [_to_entity(m) for m in result.scalars().all()]

    async def create(self, **kwargs) -> Event:
        model = EventModel(**kwargs)
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _to_entity(model)

    async def update(self, event_id: UUID, **kwargs) -> Event | None:
        result = await self._session.execute(select(EventModel).where(EventModel.id == event_id))
        model = result.scalar_one_or_none()
        if not model:
            return None
        for key, value in kwargs.items():
            if hasattr(model, key) and value is not None:
                setattr(model, key, value)
        await self._session.flush()
        await self._session.refresh(model)
        return _to_entity(model)
