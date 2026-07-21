"""Configuración pública del sitio (video del loader, etc.)."""
from time import monotonic

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tava.infrastructure.persistence.models import SiteSettingModel

KEY_LOADER_VIDEO_URL = "loader_video_url"
KEY_LOADER_VIDEO_ENABLED = "loader_video_enabled"

# Claves legacy (video de fondo difuminado — ya no se usa en el frontend)
KEY_HERO_VIDEO_URL = "hero_video_url"
KEY_HERO_VIDEO_ENABLED = "hero_video_enabled"

DEFAULT_LOADER_VIDEO = ""

_APPEARANCE_CACHE_TTL_SECONDS = 60
_appearance_cache: dict | None = None
_appearance_cache_at = 0.0


def _parse_enabled(raw: str | None, default: bool = True) -> bool:
    if raw is None:
        return default
    return raw.lower() in ("1", "true", "yes")


async def get_public_appearance(session: AsyncSession) -> dict:
    global _appearance_cache, _appearance_cache_at

    now = monotonic()
    if _appearance_cache and now - _appearance_cache_at < _APPEARANCE_CACHE_TTL_SECONDS:
        return dict(_appearance_cache)

    result = await session.execute(
        select(SiteSettingModel).where(
            SiteSettingModel.key.in_(
                [
                    KEY_LOADER_VIDEO_URL,
                    KEY_LOADER_VIDEO_ENABLED,
                    KEY_HERO_VIDEO_URL,
                    KEY_HERO_VIDEO_ENABLED,
                ]
            )
        )
    )
    rows = {r.key: r.value for r in result.scalars().all()}

    loader_url = rows.get(KEY_LOADER_VIDEO_URL)
    if loader_url is None:
        loader_url = DEFAULT_LOADER_VIDEO
    else:
        loader_url = loader_url or DEFAULT_LOADER_VIDEO

    enabled_raw = rows.get(KEY_LOADER_VIDEO_ENABLED)
    if enabled_raw is None:
        enabled = True
    else:
        enabled = _parse_enabled(enabled_raw, default=True)

    data = {
        "loader_video_url": loader_url,
        "loader_video_enabled": enabled,
    }
    _appearance_cache = data
    _appearance_cache_at = now
    return dict(data)


async def set_setting(session: AsyncSession, key: str, value: str) -> None:
    global _appearance_cache, _appearance_cache_at

    _appearance_cache = None
    _appearance_cache_at = 0.0
    result = await session.execute(select(SiteSettingModel).where(SiteSettingModel.key == key))
    row = result.scalar_one_or_none()
    if row:
        row.value = value
    else:
        session.add(SiteSettingModel(key=key, value=value))
    await session.flush()


async def ensure_default_settings(session: AsyncSession) -> None:
    result = await session.execute(
        select(SiteSettingModel).where(SiteSettingModel.key == KEY_LOADER_VIDEO_URL)
    )
    if not result.scalar_one_or_none():
        await set_setting(session, KEY_LOADER_VIDEO_URL, DEFAULT_LOADER_VIDEO)
        await set_setting(session, KEY_LOADER_VIDEO_ENABLED, "true")
