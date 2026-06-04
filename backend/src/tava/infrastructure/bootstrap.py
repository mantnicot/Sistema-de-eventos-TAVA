"""Inicialización de tablas y datos demo al arrancar la API."""
import logging
from datetime import date, time

from sqlalchemy import select

from tava.domain.enums import EventStatus, UserRole
from tava.infrastructure.persistence.database import AsyncSessionLocal, init_db
from tava.infrastructure.persistence.models import BannerModel, EventModel, UserModel
from tava.infrastructure.security.password import hash_password

logger = logging.getLogger("tava.bootstrap")


async def bootstrap_application() -> None:
    await init_db()
    async with AsyncSessionLocal() as session:
        try:
            admin_email = "admin@tavateatro.com"
            result = await session.execute(select(UserModel).where(UserModel.email == admin_email))
            admin = result.scalar_one_or_none()
            if not admin:
                admin = UserModel(
                    email=admin_email,
                    password_hash=hash_password("AdminTava2026!"),
                    full_name="Administrador TAVA",
                    role=UserRole.ADMIN,
                )
                session.add(admin)
                await session.flush()
                logger.info("Usuario admin creado: %s", admin_email)

            if not admin:
                result = await session.execute(select(UserModel).where(UserModel.email == admin_email))
                admin = result.scalar_one()
            organizer_id = admin.id

            event_result = await session.execute(
                select(EventModel).where(EventModel.name == "Noche de Estreno TAVA")
            )
            if not event_result.scalar_one_or_none():
                session.add(
                    EventModel(
                        name="Noche de Estreno TAVA",
                        description="Experiencia teatral del grupo TAVA.",
                        event_date=date(2026, 7, 15),
                        event_time=time(19, 30),
                        city="Bogotá",
                        address="Teatro TAVA",
                        category="Teatro",
                        status=EventStatus.PUBLISHED,
                        capacity=120,
                        main_image_url="/assets/events/estreno.jpg",
                        organizer_id=organizer_id,
                    )
                )

            banner_result = await session.execute(select(BannerModel).limit(1))
            if not banner_result.scalar_one_or_none():
                session.add(
                    BannerModel(
                        title="Temporada 2026 — TAVA Teatro",
                        image_url="/assets/banners/temporada.jpg",
                        link_url="/eventos",
                        banner_type="promocional",
                        sort_order=0,
                    )
                )

            await session.commit()
            logger.info("Bootstrap de datos completado")
        except Exception:
            await session.rollback()
            logger.exception("Bootstrap de datos falló")
            raise
