from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from tava.domain.enums import EventReviewStatus, EventStatus, UserRole
from tava.infrastructure.persistence.database import get_db
from tava.infrastructure.persistence.event_staff import get_event_staff, list_assigned_event_ids, set_event_staff
from tava.infrastructure.persistence.models import EventMediaModel, EventModel, TicketModel, TicketTypeModel, UserModel
from tava.infrastructure.persistence.repositories.sqlalchemy_event_repository import SQLAlchemyEventRepository
from tava.presentation.api.dependencies import get_current_user, require_roles
from tava.presentation.api.auth_helpers import can_manage_event, is_platform_admin
from tava.presentation.api.platform_auth import (
    require_event_manager,
    require_platform_admin,
)
from tava.presentation.api.schemas import (
    BroadcastEmailRequest,
    EventCarteleraRequest,
    EventCreateRequest,
    EventDetailResponse,
    EventMediaCreateRequest,
    EventMediaResponse,
    EventResponse,
    EventReviewRequest,
    EventStaffResponse,
    EventStaffUpdateRequest,
    SeatingSyncRequest,
    TheatricalDetailsSchema,
    TicketTypePublicResponse,
    TicketTypesSyncRequest,
)
from tava.application.use_cases.seating import SeatingUseCase, seating_enabled

router = APIRouter(prefix="/events", tags=["Eventos"])


def _theatrical(details: dict | None) -> TheatricalDetailsSchema | None:
    if not details:
        return None
    return TheatricalDetailsSchema.model_validate(details)


def _event_response(
    model: EventModel,
    *,
    tickets_available: int = 0,
    organizer_name: str | None = None,
    include_admin_fields: bool = False,
) -> EventResponse:
    payload = EventResponse(
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
        tickets_available=tickets_available,
    )
    if include_admin_fields:
        payload.review_status = model.review_status
        payload.cartelera_visible = model.cartelera_visible
        payload.organizer_id = model.organizer_id
        payload.organizer_name = organizer_name
        payload.rejection_reason = model.rejection_reason
    return payload


async def _organizer_names(db: AsyncSession, organizer_ids: list[UUID]) -> dict[UUID, str]:
    if not organizer_ids:
        return {}
    result = await db.execute(
        select(UserModel.id, UserModel.full_name).where(UserModel.id.in_(organizer_ids))
    )
    return {row[0]: row[1] for row in result.all()}


def _apply_organizer_publish_rules(user, data: dict, existing: EventModel | None = None) -> dict:
    if is_platform_admin(user):
        return data
    status = data.get("status", existing.status if existing else EventStatus.DRAFT)
    if status in (EventStatus.PUBLISHED, EventStatus.IN_PROGRESS, EventStatus.SOLD_OUT):
        data["status"] = EventStatus.SCHEDULED
        data["review_status"] = EventReviewStatus.PENDING
        data["cartelera_visible"] = False
    return data


async def _get_event_or_404(db: AsyncSession, event_id: UUID) -> EventModel:
    result = await db.execute(select(EventModel).where(EventModel.id == event_id))
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="Evento no encontrado")
    return model


async def _require_manage_event(db: AsyncSession, event_id: UUID, user) -> EventModel:
    model = await _get_event_or_404(db, event_id)
    if not can_manage_event(user, model):
        raise HTTPException(status_code=403, detail="No puedes gestionar este evento")
    return model


async def _tickets_available_by_event(db: AsyncSession, event_ids: list[UUID]) -> dict[UUID, int]:
    if not event_ids:
        return {}
    result = await db.execute(
        select(TicketTypeModel.event_id, func.coalesce(func.sum(TicketTypeModel.quantity_available), 0))
        .where(TicketTypeModel.event_id.in_(event_ids))
        .group_by(TicketTypeModel.event_id)
    )
    return {row[0]: int(row[1]) for row in result.all()}


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
        seating_enabled=seating_enabled(model),
    )


@router.get("", response_model=list[EventResponse])
async def list_events(
    search: str | None = None,
    category: str | None = None,
    status: EventStatus | None = None,
    limit: int = Query(20, le=100),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    repo = SQLAlchemyEventRepository(db)
    events = await repo.list_public(search=search, category=category, status=status, limit=limit, offset=offset)
    ids = [e.id for e in events]
    avail = await _tickets_available_by_event(db, ids)
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
            tickets_available=avail.get(e.id, 0),
        )
        for e in events
    ]


@router.get("/admin/all", response_model=list[EventResponse])
async def list_events_admin(
    status: EventStatus | None = None,
    limit: int = Query(200, le=500),
    offset: int = 0,
    user=Depends(require_event_manager),
    db: AsyncSession = Depends(get_db),
):
    q = select(EventModel).order_by(EventModel.event_date.desc()).limit(limit).offset(offset)
    if not is_platform_admin(user):
        q = q.where(EventModel.organizer_id == user.id)
    if status:
        q = q.where(EventModel.status == status)
    result = await db.execute(q)
    models = list(result.scalars().all())
    organizer_map = await _organizer_names(db, [m.organizer_id for m in models])
    return [
        _event_response(
            m,
            include_admin_fields=True,
            organizer_name=organizer_map.get(m.organizer_id),
        )
        for m in models
    ]


@router.get("/admin/review-queue", response_model=list[EventResponse])
async def list_review_queue(
    _user=Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(EventModel)
        .where(EventModel.review_status == EventReviewStatus.PENDING)
        .order_by(EventModel.created_at.desc())
    )
    models = list(result.scalars().all())
    organizer_map = await _organizer_names(db, [m.organizer_id for m in models])
    return [
        _event_response(
            m,
            include_admin_fields=True,
            organizer_name=organizer_map.get(m.organizer_id),
        )
        for m in models
    ]


@router.get("/admin/review-pending-count")
async def review_pending_count(
    _user=Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(func.count())
        .select_from(EventModel)
        .where(EventModel.review_status == EventReviewStatus.PENDING)
    )
    return {"count": int(result.scalar_one() or 0)}


@router.patch("/{event_id}/review", response_model=EventResponse)
async def review_event(
    event_id: UUID,
    body: EventReviewRequest,
    user=Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    model = await _get_event_or_404(db, event_id)
    now = datetime.now(UTC)
    if body.action == "approve":
        model.review_status = EventReviewStatus.APPROVED
        model.rejection_reason = None
        model.status = EventStatus.PUBLISHED
        if body.cartelera_visible is not None:
            model.cartelera_visible = body.cartelera_visible
        else:
            model.cartelera_visible = True
    else:
        model.review_status = EventReviewStatus.REJECTED
        model.rejection_reason = body.rejection_reason or "Revisión rechazada"
        model.cartelera_visible = False
        if model.status == EventStatus.PUBLISHED:
            model.status = EventStatus.SCHEDULED
    model.reviewed_at = now
    model.reviewed_by = user.id
    await db.flush()
    organizer_map = await _organizer_names(db, [model.organizer_id])
    return _event_response(
        model,
        include_admin_fields=True,
        organizer_name=organizer_map.get(model.organizer_id),
    )


@router.patch("/{event_id}/cartelera", response_model=EventResponse)
async def set_cartelera_visibility(
    event_id: UUID,
    body: EventCarteleraRequest,
    _user=Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    model = await _get_event_or_404(db, event_id)
    if body.visible and model.review_status != EventReviewStatus.APPROVED:
        raise HTTPException(status_code=400, detail="Solo eventos aprobados pueden mostrarse en cartelera")
    model.cartelera_visible = body.visible
    await db.flush()
    organizer_map = await _organizer_names(db, [model.organizer_id])
    return _event_response(
        model,
        include_admin_fields=True,
        organizer_name=organizer_map.get(model.organizer_id),
    )


@router.post("/{event_id}/submit-review")
async def submit_event_for_review(
    event_id: UUID,
    user=Depends(require_event_manager),
    db: AsyncSession = Depends(get_db),
):
    from tava.application.use_cases.event_notifications import EventNotificationUseCase

    model = await _require_manage_event(db, event_id, user)
    review_notification: dict | None = None
    if is_platform_admin(user):
        model.review_status = EventReviewStatus.APPROVED
        model.cartelera_visible = True
        if model.status == EventStatus.DRAFT:
            model.status = EventStatus.PUBLISHED
    else:
        was_pending = model.review_status == EventReviewStatus.PENDING
        model.review_status = EventReviewStatus.PENDING
        model.cartelera_visible = False
        model.rejection_reason = None
        if model.status == EventStatus.DRAFT:
            model.status = EventStatus.SCHEDULED
        await db.flush()
        if not was_pending:
            notify_uc = EventNotificationUseCase(db)
            organizer_result = await db.execute(select(UserModel).where(UserModel.id == user.id))
            review_notification = await notify_uc.notify_platform_admin_review_request(
                model,
                organizer=organizer_result.scalar_one_or_none(),
            )
    await db.flush()
    await db.commit()
    organizer_map = await _organizer_names(db, [model.organizer_id])
    response = _event_response(
        model,
        include_admin_fields=True,
        organizer_name=organizer_map.get(model.organizer_id),
    )
    payload = response.model_dump()
    if review_notification is not None:
        payload["review_notification"] = review_notification
    return payload


@router.get("/assigned/mine", response_model=list[EventResponse])
async def my_assigned_events(
    staff_role: str = Query(..., pattern="^(validator|seller)$"),
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if is_platform_admin(user):
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
    user=Depends(require_platform_admin),
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
    user=Depends(require_platform_admin),
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
    is_public = (
        model.review_status == EventReviewStatus.APPROVED
        and model.cartelera_visible
        and model.status not in (EventStatus.DRAFT, EventStatus.CANCELLED)
    )
    if not is_public:
        raise HTTPException(status_code=404, detail="Evento no encontrado")
    return _event_detail(model)


@router.get("/{event_id}/manage", response_model=EventDetailResponse)
async def get_event_for_manage(
    event_id: UUID,
    user=Depends(require_event_manager),
    db: AsyncSession = Depends(get_db),
):
    model = await _require_manage_event(db, event_id, user)
    result = await db.execute(
        select(EventModel)
        .where(EventModel.id == model.id)
        .options(selectinload(EventModel.gallery), selectinload(EventModel.ticket_types))
    )
    loaded = result.scalar_one()
    return _event_detail(loaded)


@router.post("", response_model=EventResponse)
async def create_event(
    body: EventCreateRequest,
    user=Depends(require_event_manager),
    db: AsyncSession = Depends(get_db),
):
    repo = SQLAlchemyEventRepository(db)
    data = body.model_dump()
    if body.theatrical_details:
        data["theatrical_details"] = body.theatrical_details.model_dump()
    else:
        data.pop("theatrical_details", None)
    data["organizer_id"] = user.id
    if is_platform_admin(user):
        data["review_status"] = EventReviewStatus.APPROVED
        if data.get("status") in (EventStatus.PUBLISHED, EventStatus.IN_PROGRESS):
            data["cartelera_visible"] = True
    else:
        data["review_status"] = EventReviewStatus.PENDING
        data["cartelera_visible"] = False
        data = _apply_organizer_publish_rules(user, data)
    event = await repo.create(**data)
    result = await db.execute(select(EventModel).where(EventModel.id == event.id))
    return _event_response(result.scalar_one(), include_admin_fields=True)


@router.patch("/{event_id}")
async def update_event(
    event_id: UUID,
    body: EventCreateRequest,
    user=Depends(require_event_manager),
    db: AsyncSession = Depends(get_db),
):
    from tava.application.use_cases.event_notifications import EventNotificationUseCase

    before_model = await _require_manage_event(db, event_id, user)

    repo = SQLAlchemyEventRepository(db)
    data = body.model_dump(exclude_unset=True)
    if body.theatrical_details is not None:
        data["theatrical_details"] = body.theatrical_details.model_dump()
    data = _apply_organizer_publish_rules(user, data, before_model)
    if not is_platform_admin(user) and before_model.review_status == EventReviewStatus.REJECTED:
        data["review_status"] = EventReviewStatus.PENDING
        data["rejection_reason"] = None
    event = await repo.update(event_id, **data)
    if not event:
        raise HTTPException(status_code=404, detail="Evento no encontrado")
    result = await db.execute(select(EventModel).where(EventModel.id == event_id))
    after_model = result.scalar_one()

    notify_uc = EventNotificationUseCase(db)
    notification = await notify_uc.on_event_updated(before_model, after_model)
    review_notification = None
    if (
        not is_platform_admin(user)
        and after_model.review_status == EventReviewStatus.PENDING
        and before_model.review_status != EventReviewStatus.PENDING
    ):
        organizer_result = await db.execute(select(UserModel).where(UserModel.id == user.id))
        review_notification = await notify_uc.notify_platform_admin_review_request(
            after_model,
            organizer=organizer_result.scalar_one_or_none(),
        )
    await db.commit()

    response = _event_response(after_model, include_admin_fields=True)
    payload = response.model_dump()
    payload["attendee_notification"] = notification
    if review_notification is not None:
        payload["review_notification"] = review_notification
    return payload


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
    user=Depends(require_event_manager),
    db: AsyncSession = Depends(get_db),
):
    event = await _require_manage_event(db, event_id, user)

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
        if item.id and item.id in existing:
            model = existing[item.id]
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
    user=Depends(require_event_manager),
    db: AsyncSession = Depends(get_db),
):
    await _require_manage_event(db, event_id, user)
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


@router.get("/{event_id}/seating")
async def get_event_seating(event_id: UUID, db: AsyncSession = Depends(get_db)):
    uc = SeatingUseCase(db)
    return await uc.get_map(event_id)


@router.put("/{event_id}/seating")
async def sync_event_seating(
    event_id: UUID,
    body: SeatingSyncRequest,
    user=Depends(require_event_manager),
    db: AsyncSession = Depends(get_db),
):
    uc = SeatingUseCase(db)
    try:
        result = await uc.sync_layout(event_id, body.seating.model_dump())
        await db.commit()
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{event_id}/broadcast-email")
async def broadcast_event_email(
    event_id: UUID,
    body: BroadcastEmailRequest,
    user=Depends(require_event_manager),
    db: AsyncSession = Depends(get_db),
):
    await _require_manage_event(db, event_id, user)
    from tava.application.use_cases.event_notifications import EventNotificationUseCase

    uc = EventNotificationUseCase(db)
    try:
        result = await uc.broadcast_custom_email(
            event_id, subject=body.subject, message=body.message
        )
        await db.commit()
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{event_id}")
async def delete_event(
    event_id: UUID,
    user=Depends(require_event_manager),
    db: AsyncSession = Depends(get_db),
):
    from tava.infrastructure.persistence.models import TicketModel

    event = await _require_manage_event(db, event_id, user)
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
