"""Limpia datos de prueba y deja solo dos usuarios base."""
import logging

from sqlalchemy import delete, select

from tava.domain.enums import UserRole
from tava.infrastructure.persistence.models import (
    BannerModel,
    CheckInModel,
    CollectibleModel,
    EmailVerificationTokenModel,
    EventMediaModel,
    EventModel,
    EventSeatModel,
    EventStaffAssignmentModel,
    FavoriteModel,
    LoyaltyRewardModel,
    OrderModel,
    PasswordResetTokenModel,
    PromotionModel,
    RefreshTokenModel,
    ReviewModel,
    SeatModel,
    SectorModel,
    SiteSettingModel,
    TicketModel,
    TicketTypeModel,
    UserModel,
    VenueModel,
)
from tava.infrastructure.security.password import hash_password

logger = logging.getLogger("tava.demo_reset")

ADMIN_EMAIL = "admin@tavateatro.com"
TEST_EMAIL = "prueba@tavateatro.com"
TEST_PASSWORD = "PruebaTava2026!"
ADMIN_PASSWORD = "AdminTava2026!"

RESET_MARKER_KEY = "demo_reset_marker"
RESET_MARKER_VALUE = "2026-06-clean-v1"
EVENT_CLEANUP_MARKER_KEY = "demo_event_cleanup_marker"
EVENT_CLEANUP_MARKER_VALUE = "2026-07-remove-test-events-v1"
DEMO_EVENT_NAMES_TO_DELETE = ("Prueba de evento pago", "Laboratorio de impro")


async def cleanup_demo_events(session, *, force: bool = False) -> int:
    """Elimina eventos demo puntuales sin reiniciar toda la base."""
    marker = await session.get(SiteSettingModel, EVENT_CLEANUP_MARKER_KEY)
    if marker and marker.value == EVENT_CLEANUP_MARKER_VALUE and not force:
        logger.info("Limpieza de eventos demo ya aplicada (%s)", EVENT_CLEANUP_MARKER_VALUE)
        return 0

    result = await session.execute(
        select(EventModel.id).where(EventModel.name.in_(DEMO_EVENT_NAMES_TO_DELETE))
    )
    event_ids = [row[0] for row in result.all()]
    if not event_ids:
        deleted = 0
    else:
        ticket_result = await session.execute(
            select(TicketModel.id).where(TicketModel.event_id.in_(event_ids))
        )
        ticket_ids = [row[0] for row in ticket_result.all()]
        if ticket_ids:
            await session.execute(
                delete(CheckInModel).where(CheckInModel.ticket_id.in_(ticket_ids))
            )
        await session.execute(delete(CheckInModel).where(CheckInModel.event_id.in_(event_ids)))
        await session.execute(delete(TicketModel).where(TicketModel.event_id.in_(event_ids)))
        await session.execute(delete(OrderModel).where(OrderModel.event_id.in_(event_ids)))
        await session.execute(
            delete(EventStaffAssignmentModel).where(EventStaffAssignmentModel.event_id.in_(event_ids))
        )
        await session.execute(delete(EventMediaModel).where(EventMediaModel.event_id.in_(event_ids)))
        await session.execute(delete(TicketTypeModel).where(TicketTypeModel.event_id.in_(event_ids)))
        await session.execute(delete(ReviewModel).where(ReviewModel.event_id.in_(event_ids)))
        await session.execute(delete(FavoriteModel).where(FavoriteModel.event_id.in_(event_ids)))
        await session.execute(delete(CollectibleModel).where(CollectibleModel.event_id.in_(event_ids)))
        await session.execute(delete(PromotionModel).where(PromotionModel.event_id.in_(event_ids)))
        await session.execute(delete(EventSeatModel).where(EventSeatModel.event_id.in_(event_ids)))
        await session.execute(delete(SeatModel).where(SeatModel.event_id.in_(event_ids)))
        await session.execute(delete(EventModel).where(EventModel.id.in_(event_ids)))
        deleted = len(event_ids)

    if marker:
        marker.value = EVENT_CLEANUP_MARKER_VALUE
    else:
        session.add(SiteSettingModel(key=EVENT_CLEANUP_MARKER_KEY, value=EVENT_CLEANUP_MARKER_VALUE))

    await session.flush()
    logger.info("Eventos demo eliminados: %s", deleted)
    return deleted


async def reset_demo_data(session, *, force: bool = False) -> bool:
    """Borra eventos, medios, boletas y usuarios extra. Retorna True si ejecutó el reset."""
    marker = await session.get(SiteSettingModel, RESET_MARKER_KEY)
    if marker and marker.value == RESET_MARKER_VALUE and not force:
        logger.info("Reset demo ya aplicado (%s)", RESET_MARKER_VALUE)
        return False

    logger.warning("Ejecutando reset demo: solo quedarán admin y usuario de prueba")

    await session.execute(delete(CheckInModel))
    await session.execute(delete(TicketModel))
    await session.execute(delete(OrderModel))
    await session.execute(delete(EventStaffAssignmentModel))
    await session.execute(delete(EventMediaModel))
    await session.execute(delete(TicketTypeModel))
    await session.execute(delete(EventSeatModel))
    await session.execute(delete(ReviewModel))
    await session.execute(delete(FavoriteModel))
    await session.execute(delete(CollectibleModel))
    await session.execute(delete(PromotionModel))
    await session.execute(delete(SeatModel))
    await session.execute(delete(SectorModel))
    await session.execute(delete(EventModel))
    await session.execute(delete(BannerModel))
    await session.execute(delete(VenueModel))
    await session.execute(delete(LoyaltyRewardModel))
    await session.execute(delete(RefreshTokenModel))
    await session.execute(delete(EmailVerificationTokenModel))
    await session.execute(delete(PasswordResetTokenModel))

    await session.execute(
        delete(UserModel).where(UserModel.email.notin_([ADMIN_EMAIL, TEST_EMAIL]))
    )

    # Limpiar video/imágenes de apariencia
    for key in ("loader_video_url", "loader_video_enabled"):
        row = await session.get(SiteSettingModel, key)
        if row:
            if key == "loader_video_url":
                row.value = ""
            else:
                row.value = "true"

    admin = (
        await session.execute(select(UserModel).where(UserModel.email == ADMIN_EMAIL))
    ).scalar_one_or_none()
    if not admin:
        admin = UserModel(
            email=ADMIN_EMAIL,
            password_hash=hash_password(ADMIN_PASSWORD),
            full_name="Administrador TAVA",
            role=UserRole.ADMIN,
            email_verified=True,
        )
        session.add(admin)
    else:
        admin.role = UserRole.ADMIN
        admin.email_verified = True
        admin.password_hash = hash_password(ADMIN_PASSWORD)

    test_user = (
        await session.execute(select(UserModel).where(UserModel.email == TEST_EMAIL))
    ).scalar_one_or_none()
    if not test_user:
        test_user = UserModel(
            email=TEST_EMAIL,
            password_hash=hash_password(TEST_PASSWORD),
            full_name="Usuario Prueba TAVA",
            role=UserRole.GENERAL,
            email_verified=True,
        )
        session.add(test_user)
    else:
        test_user.role = UserRole.GENERAL
        test_user.email_verified = True
        test_user.password_hash = hash_password(TEST_PASSWORD)

    if marker:
        marker.value = RESET_MARKER_VALUE
    else:
        session.add(SiteSettingModel(key=RESET_MARKER_KEY, value=RESET_MARKER_VALUE))

    await session.flush()
    logger.info("Reset demo completado. Usuarios: %s, %s", ADMIN_EMAIL, TEST_EMAIL)
    return True
