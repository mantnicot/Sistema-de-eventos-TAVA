"""Subida de imágenes y videos — local o Cloudinary (persistente)."""
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile

from tava.config import get_settings
from tava.domain.enums import UserRole
from tava.infrastructure.services.cloudinary_storage import cloudinary_configured, upload_bytes
from tava.presentation.api.dependencies import require_roles

logger = logging.getLogger("tava.media")

router = APIRouter(prefix="/media", tags=["Archivos multimedia"])

ALLOWED_IMAGE = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
ALLOWED_VIDEO = {".mp4", ".webm", ".mov", ".m4v"}
MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_VIDEO_BYTES = 80 * 1024 * 1024


def _public_url(relative_path: str) -> str:
    settings = get_settings()
    base = (settings.api_public_base_url or "").rstrip("/")
    if base:
        return f"{base}{relative_path}"
    return relative_path


@router.post("/upload")
async def upload_media(
    file: UploadFile = File(...),
    kind: str = Query("image", pattern="^(image|video)$"),
    _user=Depends(require_roles(UserRole.ADMIN)),
):
    settings = get_settings()
    suffix = Path(file.filename or "").suffix.lower()
    allowed = ALLOWED_IMAGE if kind == "image" else ALLOWED_VIDEO
    if suffix not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Formato no permitido. Usa: {', '.join(sorted(allowed))}",
        )

    content = await file.read()
    max_size = MAX_IMAGE_BYTES if kind == "image" else MAX_VIDEO_BYTES
    if len(content) > max_size:
        raise HTTPException(status_code=400, detail=f"Archivo demasiado grande (máx. {max_size // (1024*1024)} MB)")

    safe_name = f"{uuid.uuid4().hex}{suffix}"
    resource_type = "image" if kind == "image" else "video"
    sub = "images" if kind == "image" else "videos"

    # Cloudinary primero en producción (archivos no se pierden al redeploy)
    if cloudinary_configured():
        cloud_url = await upload_bytes(
            content,
            resource_type=resource_type,
            filename=safe_name,
            folder=sub,
        )
        if cloud_url:
            return {
                "url": cloud_url,
                "path": cloud_url,
                "filename": safe_name,
                "media_type": kind,
                "size": len(content),
                "storage": "cloudinary",
            }
        logger.warning("Cloudinary configurado pero falló la subida; usando disco local")

    upload_dir = Path(settings.uploads_dir)
    target_dir = upload_dir / sub
    target_dir.mkdir(parents=True, exist_ok=True)
    dest = target_dir / safe_name
    dest.write_bytes(content)

    relative = f"/uploads/{sub}/{safe_name}"
    url = _public_url(relative)
    logger.info("Archivo en disco local: %s (%s bytes)", relative, len(content))
    if settings.app_env == "production" and not cloudinary_configured():
        logger.warning(
            "PRODUCCIÓN sin Cloudinary: los archivos en /uploads se pierden al redeploy de Render. "
            "Define CLOUDINARY_CLOUD_NAME y CLOUDINARY_UPLOAD_PRESET."
        )

    return {
        "url": url,
        "path": relative,
        "filename": safe_name,
        "media_type": kind,
        "size": len(content),
        "storage": "local",
    }
