from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from tava.domain.enums import EventStatus, UserRole
from tava.infrastructure.persistence.database import get_db
from tava.infrastructure.persistence.models import EventModel, TicketTypeModel
from tava.infrastructure.persistence.repositories.sqlalchemy_event_repository import SQLAlchemyEventRepository
from tava.presentation.api.dependencies import get_current_user, require_roles
from tava.presentation.api.schemas import (
    EventCreateRequest,
    EventDetailResponse,
    EventMediaResponse,
    EventResponse,
    TheatricalDetailsSchema,
    TicketTypePublicResponse,
)

router = APIRouter(prefix="/events", tags=["Eventos"])


def _theatrical(details: dict | None) -> TheatricalDetailsSchema | None:
    if not details:
        return None
    return TheatricalDetailsSchema.model_validate(details)


def _event_response(model: EventModel) -> EventResponse:
    return EventResponse(
        id=model.id,
        name=model.name,
        description=model.description,
        event_date=model.event_date,
        event_time=model.event_time,
        city=model.city,
        address=model.address,
        category=model.category,
        status=model.status,
        capacity=model.capacity,
        main_image_url=model.main_image_url,
        trailer_url=model.trailer_url,
        theatrical_details=_theatrical(model.theatrical_details),
    )


def _event_detail(model: EventModel) -> EventDetailResponse:
    base = _event_response(model)
    return EventDetailResponse(
        **base.model_dump(),
        gallery=[
            EventMediaResponse(
                id=m.id, media_type=m.media_type, url=m.url, sort_order=m.sort_order
            )
            for m in sorted(model.gallery, key=lambda x: x.sort_order)
        ],
        ticket_types=[
            TicketTypePublicResponse(
                id=t.id,
                name=t.name,
                kind=t.kind,
                price=t.price,
                quantity_available=t.quantity_available,
                benefits=t.benefits,
            )
            for t in model.ticket_types
        ],
    )


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
    return [
        EventResponse(
            id=e.id,
            name=e.name,
            description=e.description,
            event_date=e.event_date,
            event_time=e.event_time,
            city=e.city,
            address=e.address,
            category=e.category,
            status=e.status,
            capacity=e.capacity,
            main_image_url=e.main_image_url,
            trailer_url=e.trailer_url,
            theatrical_details=_theatrical(e.theatrical_details),
        )
        for e in events
    ]


@router.get("/admin/all", response_model=list[EventResponse])
async def list_events_admin(
    status: EventStatus | None = None,
    limit: int = Query(50, le=100),
    offset: int = 0,
    _user=Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    q = select(EventModel).order_by(EventModel.event_date.desc()).limit(limit).offset(offset)
    if status:
        q = q.where(EventModel.status == status)
    result = await db.execute(q)
    return [_event_response(m) for m in result.scalars().all()]


@router.get("/{event_id}", response_model=EventDetailResponse)
async def get_event(event_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(EventModel)
        .where(EventModel.id == event_id)
        .options(selectinload(EventModel.gallery), selectinload(EventModel.ticket_types))
    )
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="Evento no encontrado")
    return _event_detail(model)


@router.post("", response_model=EventResponse)
async def create_event(
    body: EventCreateRequest,
    user=Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    repo = SQLAlchemyEventRepository(db)
    data = body.model_dump()
    if body.theatrical_details:
        data["theatrical_details"] = body.theatrical_details.model_dump()
    else:
        data.pop("theatrical_details", None)
    data["organizer_id"] = user.id
    event = await repo.create(**data)
    result = await db.execute(select(EventModel).where(EventModel.id == event.id))
    return _event_response(result.scalar_one())


@router.patch("/{event_id}", response_model=EventResponse)
async def update_event(
    event_id: UUID,
    body: EventCreateRequest,
    user=Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    repo = SQLAlchemyEventRepository(db)
    data = body.model_dump(exclude_unset=True)
    if body.theatrical_details is not None:
        data["theatrical_details"] = body.theatrical_details.model_dump()
    event = await repo.update(event_id, **data)
    if not event:
        raise HTTPException(status_code=404, detail="Evento no encontrado")
    result = await db.execute(select(EventModel).where(EventModel.id == event_id))
    return _event_response(result.scalar_one())
