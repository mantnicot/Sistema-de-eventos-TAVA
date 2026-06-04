"""Configuración pública del sitio (video de fondo, etc.)."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tava.infrastructure.persistence.models import SiteSettingModel

KEY_HERO_VIDEO_URL = "hero_video_url"
KEY_HERO_VIDEO_ENABLED = "hero_video_enabled"

DEFAULT_HERO_VIDEO = (
    "https://videos.pexels.com/video-files/2795406/2795406-hd_1920_1080_25fps.mp4"
)


async def get_public_appearance(session: AsyncSession) -> dict:
    result = await session.execute(
        select(SiteSettingModel).where(
            SiteSettingModel.key.in_([KEY_HERO_VIDEO_URL, KEY_HERO_VIDEO_ENABLED])
        )
    )
    rows = {r.key: r.value for r in result.scalars().all()}
    enabled = rows.get(KEY_HERO_VIDEO_ENABLED, "true").lower() in ("1", "true", "yes")
    return {
        "hero_video_url": rows.get(KEY_HERO_VIDEO_URL) or DEFAULT_HERO_VIDEO,
        "hero_video_enabled": enabled,
    }


async def set_setting(session: AsyncSession, key: str, value: str) -> None:
    result = await session.execute(select(SiteSettingModel).where(SiteSettingModel.key == key))
    row = result.scalar_one_or_none()
    if row:
        row.value = value
    else:
        session.add(SiteSettingModel(key=key, value=value))
    await session.flush()


async def ensure_default_settings(session: AsyncSession) -> None:
    result = await session.execute(
        select(SiteSettingModel).where(SiteSettingModel.key == KEY_HERO_VIDEO_URL)
    )
    if not result.scalar_one_or_none():
        await set_setting(session, KEY_HERO_VIDEO_URL, DEFAULT_HERO_VIDEO)
        await set_setting(session, KEY_HERO_VIDEO_ENABLED, "true")
