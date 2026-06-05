"""Almacenamiento persistente en Cloudinary (recomendado en Render)."""
import hashlib
import logging
import time
from typing import Literal

import httpx

from tava.config import get_settings

logger = logging.getLogger("tava.cloudinary")


def cloudinary_configured() -> bool:
    s = get_settings()
    if s.cloudinary_cloud_name.strip() and s.cloudinary_upload_preset.strip():
        return True
    return bool(
        s.cloudinary_cloud_name.strip()
        and s.cloudinary_api_key.strip()
        and s.cloudinary_api_secret.strip()
    )


def _signature(params: dict[str, str], api_secret: str) -> str:
    payload = "&".join(f"{k}={params[k]}" for k in sorted(params))
    return hashlib.sha1((payload + api_secret).encode()).hexdigest()


async def upload_bytes(
    content: bytes,
    *,
    resource_type: Literal["image", "video"],
    filename: str,
    folder: str,
) -> str | None:
    """Sube a Cloudinary y devuelve secure_url, o None si no está configurado."""
    settings = get_settings()
    cloud = settings.cloudinary_cloud_name.strip()
    if not cloud:
        return None

    preset = settings.cloudinary_upload_preset.strip()
    api_key = settings.cloudinary_api_key.strip()
    api_secret = settings.cloudinary_api_secret.strip()
    subfolder = f"tava/{folder}"

    data: dict[str, str] = {"folder": subfolder}
    if preset:
        data["upload_preset"] = preset
    elif api_key and api_secret:
        timestamp = str(int(time.time()))
        data["api_key"] = api_key
        data["timestamp"] = timestamp
        sign_params = {"timestamp": timestamp, "folder": subfolder}
        data["signature"] = _signature(sign_params, api_secret)
    else:
        return None

    url = f"https://api.cloudinary.com/v1_1/{cloud}/{resource_type}/upload"
    try:
        async with httpx.AsyncClient(timeout=180) as client:
            response = await client.post(
                url,
                data=data,
                files={"file": (filename, content)},
            )
        if not response.is_success:
            logger.error("Cloudinary %s: %s", response.status_code, response.text[:500])
            return None
        body = response.json()
        secure = body.get("secure_url")
        if secure:
            logger.info("Cloudinary OK: %s (%s bytes)", secure, len(content))
        return secure
    except Exception as exc:
        logger.exception("Cloudinary upload error: %s", exc)
        return None
