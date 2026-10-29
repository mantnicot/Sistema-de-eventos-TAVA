"""Configuración pública del sitio (video del loader, etc.)."""
from time import monotonic

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tava.infrastructure.persistence.models import SiteSettingModel

KEY_LOADER_VIDEO_URL = "loader_video_url"
KEY_LOADER_VIDEO_ENABLED = "loader_video_enabled"
KEY_CAPTCHA_ENABLED = "captcha_enabled"
KEY_LOGIN_NOTICE = "login_notice"
KEY_LOGIN_NOTICE_ENABLED = "login_notice_enabled"
KEY_WOMPI_FEE_PERCENT = "wompi_fee_percent"
KEY_WOMPI_FEE_FIXED = "wompi_fee_fixed"
KEY_WOMPI_FEE_IVA = "wompi_fee_iva"

# Claves legacy (video de fondo difuminado — ya no se usa en el frontend)
KEY_HERO_VIDEO_URL = "hero_video_url"
KEY_HERO_VIDEO_ENABLED = "hero_video_enabled"

DEFAULT_LOADER_VIDEO = ""
DEFAULT_LOGIN_NOTICE = (
    "TAVA Teatro estrena el pago en línea y, con este paso, ha renovado el registro de su público. "
    "Si ya formaba parte de la casa, cree nuevamente su cuenta: permanecerá disponible para ingresar "
    "y pagar sus boletas en línea."
)

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
                    KEY_CAPTCHA_ENABLED,
                    KEY_LOGIN_NOTICE,
                    KEY_LOGIN_NOTICE_ENABLED,
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
        "captcha_enabled": _parse_enabled(rows.get(KEY_CAPTCHA_ENABLED), default=False),
        "login_notice": (
            DEFAULT_LOGIN_NOTICE
            if KEY_LOGIN_NOTICE not in rows
            else (rows.get(KEY_LOGIN_NOTICE) or "").strip()
        ),
        "login_notice_enabled": _parse_enabled(
            rows.get(KEY_LOGIN_NOTICE_ENABLED),
            default=KEY_LOGIN_NOTICE not in rows,
        ),
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


async def captcha_is_enabled(session: AsyncSession) -> bool:
    data = await get_public_appearance(session)
    return bool(data.get("captcha_enabled"))


async def get_checkout_fees(session: AsyncSession) -> dict:
    from decimal import Decimal

    from tava.domain.public_price import DEFAULT_FEE_FIXED, DEFAULT_FEE_IVA, DEFAULT_FEE_PERCENT

    result = await session.execute(
        select(SiteSettingModel).where(
            SiteSettingModel.key.in_([KEY_WOMPI_FEE_PERCENT, KEY_WOMPI_FEE_FIXED, KEY_WOMPI_FEE_IVA])
        )
    )
    rows = {r.key: r.value for r in result.scalars().all()}

    def _dec(raw: str | None, fallback: Decimal) -> Decimal:
        try:
            if raw is None or str(raw).strip() == "":
                return fallback
            return Decimal(str(raw))
        except Exception:
            return fallback

    percent = _dec(rows.get(KEY_WOMPI_FEE_PERCENT), DEFAULT_FEE_PERCENT)
    fixed = _dec(rows.get(KEY_WOMPI_FEE_FIXED), DEFAULT_FEE_FIXED)
    iva = _dec(rows.get(KEY_WOMPI_FEE_IVA), DEFAULT_FEE_IVA)
    return {
        "fee_percent": float(percent),
        "fee_fixed_cop": float(fixed),
        "fee_iva": float(iva),
        "rounding_step": 100,
    }


async def set_checkout_fees(session: AsyncSession, *, percent: float, fixed: float, iva: float) -> dict:
    await set_setting(session, KEY_WOMPI_FEE_PERCENT, str(percent))
    await set_setting(session, KEY_WOMPI_FEE_FIXED, str(fixed))
    await set_setting(session, KEY_WOMPI_FEE_IVA, str(iva))
    return await get_checkout_fees(session)


async def ensure_default_settings(session: AsyncSession) -> None:
    result = await session.execute(
        select(SiteSettingModel).where(SiteSettingModel.key == KEY_LOADER_VIDEO_URL)
    )
    if not result.scalar_one_or_none():
        await set_setting(session, KEY_LOADER_VIDEO_URL, DEFAULT_LOADER_VIDEO)
        await set_setting(session, KEY_LOADER_VIDEO_ENABLED, "true")
