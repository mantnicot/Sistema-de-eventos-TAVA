import httpx

from tava.config import get_settings

settings = get_settings()


async def verify_captcha(token: str | None) -> bool:
    """Valida captcha; en desarrollo sin clave configurada permite continuar."""
    if not settings.captcha_secret_key:
        return settings.app_env == "development"
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
