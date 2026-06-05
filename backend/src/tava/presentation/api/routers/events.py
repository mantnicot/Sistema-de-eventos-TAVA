from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from tava.domain.enums import EventStatus, UserRole
from tava.infrastructure.persistence.database import get_db
from tava.infrastructure.persistence.event_staff import get_event_staff, list_assigned_event_ids, set_event_staff
from tava.infrastructure.persistence.models import EventMediaModel, EventModel, TicketModel, TicketTypeModel
from tava.infrastructure.persistence.repositories.sqlalchemy_event_repository import SQLAlchemyEventRepository
from tava.presentation.api.dependencies import get_current_user, require_roles
from tava.presentation.api.schemas import (
    EventCreateRequest,
    EventDetailResponse,
    EventMediaCreateRequest,
    EventMediaResponse,
    EventResponse,
    EventStaffResponse,
    EventStaffUpdateRequest,
    TheatricalDetailsSchema,
    TicketTypePublicResponse,
    TicketTypesSyncRequest,
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


@router.get("/assigned/mine", response_model=list[EventResponse])
async def my_assigned_events(
    staff_role: str = Query(..., pattern="^(validator|seller)$"),
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user.role == UserRole.ADMIN:
        q = (
            select(EventModel)
            .where(EventModel.status.in_([EventStatus.PUBLISHED, EventStatus.IN_PROGRESS]))
            .order_by(EventModel.event_date.desc())
        )
        result = await db.execute(q)
        return [_event_response(m) for m in result.scalars().all()]
    if staff_role == "validator" and user.role != UserRole.VALIDATOR:
        raise HTTPException(status_code=403, detail="Rol no válido para esta consulta")
    if staff_role == "seller" and user.role != UserRole.SELLER:
        raise HTTPException(status_code=403, detail="Rol no válido para esta consulta")
    ids = await list_assigned_event_ids(db, user.id, staff_role)
    if not ids:
        return []
    result = await db.execute(
        select(EventModel).where(EventModel.id.in_(ids)).order_by(EventModel.event_date.desc())
    )
    return [_event_response(m) for m in result.scalars().all()]


@router.get("/{event_id}/staff", response_model=EventStaffResponse)
async def get_event_staff_endpoint(
    event_id: UUID,
    _user=Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(EventModel.id).where(EventModel.id == event_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Evento no encontrado")
    staff = await get_event_staff(db, event_id)
    return EventStaffResponse(
        validator_ids=[UUID(x) for x in staff["validator_ids"]],
        seller_ids=[UUID(x) for x in staff["seller_ids"]],
    )


@router.put("/{event_id}/staff", response_model=EventStaffResponse)
async def update_event_staff(
    event_id: UUID,
    body: EventStaffUpdateRequest,
    _user=Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(EventModel.id).where(EventModel.id == event_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Evento no encontrado")
    await set_event_staff(db, event_id, body.validator_ids, body.seller_ids)
    staff = await get_event_staff(db, event_id)
    return EventStaffResponse(
        validator_ids=[UUID(x) for x in staff["validator_ids"]],
        seller_ids=[UUID(x) for x in staff["seller_ids"]],
    )


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


async def _sold_counts_by_type(db: AsyncSession, event_id: UUID) -> dict[UUID, int]:
    result = await db.execute(
        select(TicketModel.ticket_type_id, func.count())
        .where(TicketModel.event_id == event_id)
        .group_by(TicketModel.ticket_type_id)
    )
    return {row[0]: int(row[1]) for row in result.all()}


@router.put("/{event_id}/ticket-types", response_model=list[TicketTypePublicResponse])
async def sync_event_ticket_types(
    event_id: UUID,
    body: TicketTypesSyncRequest,
    _user=Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(EventModel).where(EventModel.id == event_id))
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Evento no encontrado")

    items = body.ticket_types
    total_qty = sum(i.quantity_available for i in items)
    if event.capacity > 0 and total_qty > event.capacity:
        raise HTTPException(
            status_code=400,
            detail=f"La suma de cupos ({total_qty}) supera el aforo del evento ({event.capacity})",
        )

    sold = await _sold_counts_by_type(db, event_id)
    existing_result = await db.execute(select(TicketTypeModel).where(TicketTypeModel.event_id == event_id))
    existing = {t.id: t for t in existing_result.scalars().all()}
    keep_ids: set[UUID] = set()

    for item in items:
        sold_count = sold.get(item.id, 0) if item.id else 0
        if item.id and item.id in existing:
            model = existing[item.id]
            if item.quantity_available < sold_count:
                raise HTTPException(
                    status_code=400,
                    detail=f'"{model.name}": cupo mínimo {sold_count} (ya vendidas)',
                )
            model.name = item.name
            model.kind = item.kind
            model.price = item.price
            model.quantity_available = item.quantity_available
            model.benefits = item.benefits
            keep_ids.add(model.id)
        else:
            if item.id:
                raise HTTPException(status_code=400, detail="Tipo de boleta no pertenece a este evento")
            model = TicketTypeModel(
                event_id=event_id,
                name=item.name,
                kind=item.kind,
                price=item.price,
                quantity_available=item.quantity_available,
                benefits=item.benefits,
            )
            db.add(model)
            await db.flush()
            keep_ids.add(model.id)

    for tid, model in existing.items():
        if tid in keep_ids:
            continue
        if sold.get(tid, 0) > 0:
            raise HTTPException(
                status_code=400,
                detail=f'No se puede quitar "{model.name}": tiene boletas vendidas',
            )
        await db.delete(model)

    await db.flush()
    refreshed = await db.execute(select(TicketTypeModel).where(TicketTypeModel.event_id == event_id))
    types = refreshed.scalars().all()
    return [
        TicketTypePublicResponse(
            id=t.id,
            name=t.name,
            kind=t.kind,
            price=t.price,
            quantity_available=t.quantity_available,
            benefits=t.benefits,
        )
        for t in types
    ]


@router.post("/{event_id}/media", response_model=EventMediaResponse)
async def add_event_media(
    event_id: UUID,
    body: EventMediaCreateRequest,
    _user=Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(EventModel).where(EventModel.id == event_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Evento no encontrado")
    media = EventMediaModel(
        event_id=event_id,
        media_type=body.media_type,
        url=body.url,
        sort_order=body.sort_order,
    )
    db.add(media)
    await db.flush()
    await db.refresh(media)
    return EventMediaResponse(
        id=media.id, media_type=media.media_type, url=media.url, sort_order=media.sort_order
    )


@router.delete("/{event_id}")
async def delete_event(
    event_id: UUID,
    _user=Depends(require_roles(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    from tava.infrastructure.persistence.models import TicketModel

    result = await db.execute(select(EventModel).where(EventModel.id == event_id))
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Evento no encontrado")
    sold = await db.execute(select(TicketModel.id).where(TicketModel.event_id == event_id).limit(1))
    if sold.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="No se puede eliminar: el evento tiene boletas asociadas",
        )
    await db.execute(delete(EventMediaModel).where(EventMediaModel.event_id == event_id))
    await db.execute(delete(TicketTypeModel).where(TicketTypeModel.event_id == event_id))
    await db.delete(event)
    await db.flush()
    return {"message": "Evento eliminado", "success": True}
