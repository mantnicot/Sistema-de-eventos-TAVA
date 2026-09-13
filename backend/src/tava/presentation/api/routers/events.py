from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from tava.application.use_cases.settlement import SettlementUseCase
from tava.application.use_cases.ticket_emails import send_order_confirmation_email_background
from tava.application.use_cases.tickets import TicketUseCase
from tava.domain.commission_contract import (
    CONTRACT_VERSION,
    MAX_COMMISSION_RATE,
    MIN_COMMISSION_RATE,
    MIN_PAID_TICKET_COP,
    contract_text,
    is_paid_ticket_price,
    normalize_commission_rate,
)
from tava.domain.enums import EventReviewStatus, EventStatus, TicketKind, UserRole
from tava.infrastructure.persistence.database import get_db
from tava.infrastructure.persistence.event_staff import get_event_staff, list_assigned_event_ids, set_event_staff
from tava.infrastructure.persistence.models import (
    EventMediaModel,
    EventModel,
    OrderModel,
    TicketModel,
    TicketTypeModel,
    UserModel,
)
from tava.infrastructure.persistence.repositories.sqlalchemy_event_repository import SQLAlchemyEventRepository
from tava.presentation.api.dependencies import get_current_user, require_roles
from tava.presentation.api.auth_helpers import can_manage_event, is_platform_admin
from tava.presentation.api.platform_auth import (
    require_event_manager,
    require_platform_admin,
)
from tava.presentation.api.schemas import (
    CommissionContractResponse,
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
        commission_rate=model.commission_rate,
        contract_version=model.contract_version,
        contract_accepted_at=model.contract_accepted_at,
        entry_unlocked=model.entry_unlocked,
    )
    if include_admin_fields:
        payload.review_status = model.review_status
        payload.cartelera_visible = model.cartelera_visible
        payload.organizer_id = model.organizer_id
        payload.organizer_name = organizer_name
        payload.rejection_reason = model.rejection_reason
        payload.pre_settlement_fee = model.pre_settlement_fee
        payload.pre_settlement_confirmed_at = model.pre_settlement_confirmed_at
        payload.pre_settlement_notified_at = model.pre_settlement_notified_at
        payload.post_settlement_fee = model.post_settlement_fee
        payload.post_settlement_notified_at = model.post_settlement_notified_at
    return payload


def _apply_commission_fields(data: dict, body: EventCreateRequest, *, existing: EventModel | None = None) -> dict:
    """Aplica comisión/contrato. Eventos free no llevan comisión."""
    details = body.theatrical_details.model_dump() if body.theatrical_details else {}
    if str(details.get("sale_mode") or "").lower() == "free":
        data["commission_rate"] = None
        data["contract_version"] = None
        data["contract_accepted_at"] = None
        data["entry_unlocked"] = True
        return data

    # EventCreate always sends commission_rate (possibly null)
    if body.commission_rate is not None:
        rate = normalize_commission_rate(body.commission_rate)
        if not body.contract_accepted and not (existing and existing.contract_accepted_at):
            raise HTTPException(
                status_code=400,
                detail="Debes aceptar el contrato de comisión de TAVA para eventos de pago.",
            )
        data["commission_rate"] = rate
        data["contract_version"] = CONTRACT_VERSION
        data["contract_accepted_at"] = existing.contract_accepted_at if existing and existing.contract_accepted_at else datetime.now(UTC)
        # El bloqueo de ingreso ocurre 1h antes (worker); hasta entonces queda habilitado
        if existing is None:
            data["entry_unlocked"] = True
        elif existing.pre_settlement_notified_at and not existing.pre_settlement_confirmed_at:
            data["entry_unlocked"] = False
    elif body.commission_rate is None and existing is None:
        data["commission_rate"] = None
        data["entry_unlocked"] = True
    elif body.commission_rate is None and existing is not None and "commission_rate" in body.model_fields_set:
        data["commission_rate"] = None
        data["entry_unlocked"] = True

    return data


async def _organizer_names(db: AsyncSession, organizer_ids: list[UUID]) -> dict[UUID, str]:
    if not organizer_ids:
        return {}
    result = await db.execute(
        select(UserModel.id, UserModel.full_name).where(UserModel.id.in_(organizer_ids))
    )
    return {row[0]: row[1] for row in result.all()}


def _sale_mode_of(details) -> str:
    if not isinstance(details, dict):
        return "whatsapp"
    return str(details.get("sale_mode") or "whatsapp").lower()


def _organizer_money_or_tickets_changed(existing: EventModel, data: dict) -> bool:
    """True si el organizador tocó dinero, comisión, aforo o modo de venta."""
    if "commission_rate" in data:
        new_c = data["commission_rate"]
        old_c = existing.commission_rate
        if new_c is None and old_c is None:
            pass
        elif new_c is None or old_c is None:
            return True
        elif Decimal(str(new_c)) != Decimal(str(old_c)):
            return True
    if "capacity" in data and int(data["capacity"]) != int(existing.capacity):
        return True
    if "theatrical_details" in data:
        old_mode = _sale_mode_of(existing.theatrical_details)
        new_mode = _sale_mode_of(data["theatrical_details"])
        if old_mode != new_mode:
            return True
    return False


def _ticket_types_money_changed(
    existing: dict[UUID, TicketTypeModel],
    items: list,
) -> bool:
    keep_ids: set[UUID] = set()
    for item in items:
        if item.id and item.id in existing:
            keep_ids.add(item.id)
            model = existing[item.id]
            if (
                model.kind != item.kind
                or Decimal(str(model.price)) != Decimal(str(item.price))
                or int(model.quantity_available) != int(item.quantity_available)
            ):
                return True
        else:
            return True
    return any(tid not in keep_ids for tid in existing)


def _queue_event_for_review(model: EventModel) -> None:
    model.review_status = EventReviewStatus.PENDING
    model.cartelera_visible = False
    model.rejection_reason = None
    if model.status in (EventStatus.PUBLISHED, EventStatus.IN_PROGRESS, EventStatus.SOLD_OUT):
        model.status = EventStatus.SCHEDULED


def _apply_organizer_publish_rules(
    user,
    data: dict,
    existing: EventModel | None = None,
    *,
    money_or_tickets_changed: bool = False,
) -> dict:
    if is_platform_admin(user):
        return data

    # Alta nueva: siempre a revisión
    if existing is None:
        status = data.get("status", EventStatus.DRAFT)
        if status in (EventStatus.PUBLISHED, EventStatus.IN_PROGRESS, EventStatus.SOLD_OUT):
            data["status"] = EventStatus.SCHEDULED
        data["review_status"] = EventReviewStatus.PENDING
        data["cartelera_visible"] = False
        return data

    # Edición: revisión solo si cambian dinero / boletas / modo de venta
    if money_or_tickets_changed:
        data["review_status"] = EventReviewStatus.PENDING
        data["cartelera_visible"] = False
        data["rejection_reason"] = None
        status = data.get("status", existing.status)
        if status in (EventStatus.PUBLISHED, EventStatus.IN_PROGRESS, EventStatus.SOLD_OUT):
            data["status"] = EventStatus.SCHEDULED
        return data

    # Cambios cosméticos: no reabrir revisión ni bajar de cartelera
    data.pop("review_status", None)
    if data.get("cartelera_visible") is True and existing.review_status != EventReviewStatus.APPROVED:
        data["cartelera_visible"] = False
    elif "cartelera_visible" in data and not is_platform_admin(user):
        # Organizador no puede auto-publicar en cartelera
        data["cartelera_visible"] = existing.cartelera_visible

    status = data.get("status")
    if status in (EventStatus.PUBLISHED, EventStatus.IN_PROGRESS, EventStatus.SOLD_OUT):
        if existing.review_status != EventReviewStatus.APPROVED:
            data["status"] = EventStatus.SCHEDULED
            data["review_status"] = EventReviewStatus.PENDING
            data["cartelera_visible"] = False
        # Si ya estaba aprobado, puede mantener el status que envíe (p. ej. publicado)
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


@router.get("/commission-contract", response_model=CommissionContractResponse)
async def get_commission_contract():
    return CommissionContractResponse(
        version=CONTRACT_VERSION,
        text=contract_text(),
        min_rate=float(MIN_COMMISSION_RATE),
        max_rate=float(MAX_COMMISSION_RATE),
        min_paid_ticket=float(MIN_PAID_TICKET_COP),
    )


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
    data.pop("contract_accepted", None)
    if body.theatrical_details:
        data["theatrical_details"] = body.theatrical_details.model_dump()
    else:
        data.pop("theatrical_details", None)
    data["organizer_id"] = user.id
    try:
        data = _apply_commission_fields(data, body, existing=None)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if is_platform_admin(user):
        data["review_status"] = EventReviewStatus.APPROVED
        if data.get("status") in (EventStatus.PUBLISHED, EventStatus.IN_PROGRESS):
            data["cartelera_visible"] = True
        if data.get("commission_rate") is None:
            data["entry_unlocked"] = True
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
    data.pop("contract_accepted", None)
    if body.theatrical_details is not None:
        data["theatrical_details"] = body.theatrical_details.model_dump()
    try:
        data = _apply_commission_fields(data, body, existing=before_model)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    money_changed = (
        False if is_platform_admin(user) else _organizer_money_or_tickets_changed(before_model, data)
    )
    data = _apply_organizer_publish_rules(
        user, data, before_model, money_or_tickets_changed=money_changed
    )
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
    details = event.theatrical_details if isinstance(event.theatrical_details, dict) else {}
    sale_mode = str(details.get("sale_mode") or "system").lower()
    is_free_event = sale_mode == "free"

    for item in items:
        price = Decimal(str(item.price or 0))
        if is_free_event and is_paid_ticket_price(price):
            raise HTTPException(
                status_code=400,
                detail="En eventos gratuitos todas las boletas deben costar $0 (solo reserva).",
            )
        if not is_free_event and is_paid_ticket_price(price) and price < MIN_PAID_TICKET_COP:
            raise HTTPException(
                status_code=400,
                detail=f"Las boletas de pago deben costar al menos ${int(MIN_PAID_TICKET_COP):,} COP.".replace(",", "."),
            )
        if (
            not is_free_event
            and item.kind != TicketKind.COURTESY
            and is_paid_ticket_price(price)
            and event.commission_rate is None
        ):
            raise HTTPException(
                status_code=400,
                detail="Configura y acepta la comisión (8%–15%) y el contrato antes de publicar boletas de pago.",
            )

    total_qty = sum(i.quantity_available for i in items)
    if event.capacity > 0 and total_qty > event.capacity:
        raise HTTPException(
            status_code=400,
            detail=f"La suma de cupos ({total_qty}) supera el aforo del evento ({event.capacity})",
        )

    sold = await _sold_counts_by_type(db, event_id)
    existing_result = await db.execute(select(TicketTypeModel).where(TicketTypeModel.event_id == event_id))
    existing = {t.id: t for t in existing_result.scalars().all()}
    tickets_money_changed = _ticket_types_money_changed(existing, items)
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

    if not is_platform_admin(user) and tickets_money_changed:
        prev_review = event.review_status
        _queue_event_for_review(event)
        await db.flush()
        if prev_review != EventReviewStatus.PENDING:
            from tava.application.use_cases.event_notifications import EventNotificationUseCase

            notify_uc = EventNotificationUseCase(db)
            organizer_result = await db.execute(select(UserModel).where(UserModel.id == user.id))
            await notify_uc.notify_platform_admin_review_request(
                event,
                organizer=organizer_result.scalar_one_or_none(),
            )

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


@router.get("/{event_id}/settlement")
async def event_settlement(
    event_id: UUID,
    user=Depends(require_event_manager),
    db: AsyncSession = Depends(get_db),
):
    await _require_manage_event(db, event_id, user)
    event = await db.get(EventModel, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Evento no encontrado")
    return await SettlementUseCase(db).settlement_snapshot(event)


@router.post("/{event_id}/settlement/confirm")
async def confirm_event_settlement(
    event_id: UUID,
    user=Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await SettlementUseCase(db).confirm_pre_settlement(event_id, user.id)
        await db.commit()
        return result
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/{event_id}/whatsapp-orders")
async def list_whatsapp_orders(
    event_id: UUID,
    user=Depends(require_event_manager),
    db: AsyncSession = Depends(get_db),
):
    await _require_manage_event(db, event_id, user)
    return {"items": await TicketUseCase(db).list_pending_whatsapp_orders(event_id)}


@router.post("/{event_id}/whatsapp-orders/{order_id}/confirm")
async def confirm_whatsapp_order(
    event_id: UUID,
    order_id: UUID,
    background_tasks: BackgroundTasks,
    user=Depends(require_event_manager),
    db: AsyncSession = Depends(get_db),
):
    await _require_manage_event(db, event_id, user)
    uc = TicketUseCase(db)
    try:
        order_check = await db.get(OrderModel, order_id)
        if not order_check or order_check.event_id != event_id:
            raise HTTPException(status_code=404, detail="Orden no encontrada en este evento")
        result = await uc.confirm_whatsapp_payment(order_id, manager_id=user.id)
        await db.commit()
        if result.get("email_pending") and result.get("order_id"):
            background_tasks.add_task(
                send_order_confirmation_email_background,
                UUID(str(result["order_id"])),
            )
        return result
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e)) from e
