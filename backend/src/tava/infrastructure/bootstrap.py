"""Inicialización de tablas y datos mínimos al arrancar la API."""
import logging

from sqlalchemy import select

from tava.domain.enums import UserRole
from tava.infrastructure.demo_reset import (
    ADMIN_EMAIL,
    ADMIN_PASSWORD,
    TEST_EMAIL,
    TEST_PASSWORD,
    cleanup_demo_events,
    reset_demo_data,
)
from tava.infrastructure.persistence.database import AsyncSessionLocal, init_db
from tava.infrastructure.persistence.models import UserModel
from tava.infrastructure.services.site_settings import ensure_default_settings
from tava.infrastructure.security.password import hash_password, verify_password

logger = logging.getLogger("tava.bootstrap")


async def bootstrap_application() -> None:
    await init_db()
    async with AsyncSessionLocal() as session:
        try:
            await reset_demo_data(session)
            await cleanup_demo_events(session)

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
                admin.email_verified = True
                if not verify_password(ADMIN_PASSWORD, admin.password_hash):
                    admin.password_hash = hash_password(ADMIN_PASSWORD)

            test_user = (
                await session.execute(select(UserModel).where(UserModel.email == TEST_EMAIL))
            ).scalar_one_or_none()
            if not test_user:
                session.add(
                    UserModel(
                        email=TEST_EMAIL,
                        password_hash=hash_password(TEST_PASSWORD),
                        full_name="Usuario Prueba TAVA",
                        role=UserRole.GENERAL,
                        email_verified=True,
                    )
                )

            await ensure_default_settings(session)
            from tava.infrastructure.security.ticket_codes import backfill_missing_ticket_codes

            filled = await backfill_missing_ticket_codes(session)
            if filled:
                logger.info("Códigos numéricos asignados a %s boletas existentes", filled)
            from tava.application.use_cases.tickets import TicketUseCase

            claim_codes = await TicketUseCase(session).backfill_missing_claim_codes()
            if claim_codes:
                logger.info("CÃ³digos de reclamo asignados a %s Ã³rdenes pagadas", claim_codes)

            await session.commit()
            logger.info("Bootstrap completado (modo pruebas, sin eventos demo)")
        except Exception:
            await session.rollback()
            logger.exception("Bootstrap de datos falló")
            raise
