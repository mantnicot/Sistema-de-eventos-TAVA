from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from tava.infrastructure.persistence.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession

from tava.domain.enums import EventStatus, UserRole
from tava.infrastructure.persistence.repositories.sqlalchemy_event_repository import SQLAlchemyEventRepository
from tava.presentation.api.dependencies import get_current_user, require_roles
from tava.presentation.api.schemas import EventCreateRequest, EventResponse

router = APIRouter(prefix="/events", tags=["Eventos"])


@router.get("", response_model=list[EventResponse])
async def list_events(
    search: str | None = None,
    category: str | None = None,
    status: EventStatus | None = EventStatus.PUBLISHED,
    limit: int = Query(20, le=100),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    repo = SQLAlchemyEventRepository(db)
    events = await repo.list_public(search=search, category=category, status=status, limit=limit, offset=offset)
    return [EventResponse.model_validate(e) for e in events]


@router.get("/{event_id}", response_model=EventResponse)
async def get_event(event_id: UUID, db: AsyncSession = Depends(get_db)):
    repo = SQLAlchemyEventRepository(db)
    event = await repo.get_by_id(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Evento no encontrado")
    return EventResponse.model_validate(event)


@router.post("", response_model=EventResponse)
async def create_event(
    body: EventCreateRequest,
    user=Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    repo = SQLAlchemyEventRepository(db)
    event = await repo.create(organizer_id=user.id, **body.model_dump())
    return EventResponse.model_validate(event)


@router.patch("/{event_id}", response_model=EventResponse)
async def update_event(
    event_id: UUID,
    body: EventCreateRequest,
    user=Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    repo = SQLAlchemyEventRepository(db)
    event = await repo.update(event_id, **body.model_dump(exclude_unset=True))
    if not event:
        raise HTTPException(status_code=404, detail="Evento no encontrado")
    return EventResponse.model_validate(event)
