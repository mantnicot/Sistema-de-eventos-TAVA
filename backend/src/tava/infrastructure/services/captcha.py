import httpx

from tava.config import get_settings

settings = get_settings()


async def ensure_captcha(session, token: str | None) -> bool:
    """Si el admin apagó el captcha en Apariencia, el ingreso no lo exige."""
    from tava.infrastructure.services.site_settings import captcha_is_enabled

    if not await captcha_is_enabled(session):
        return True
    return await verify_captcha(token)


async def verify_captcha(token: str | None) -> bool:
    """Valida captcha. Si no hay clave configurada, se omite (desarrollo y MVP producción)."""
    if not settings.captcha_secret_key:
        return True
    if not token:
        return False
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://hcaptcha.com/siteverify",
            data={"secret": settings.captcha_secret_key, "response": token},
            timeout=10.0,
        )
        data = resp.json()
        return bool(data.get("success"))
