from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PRODUCTION_FRONTEND_URL = "https://sistema-de-eventos-tava.vercel.app"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "TAVA — Gestión de Eventos y Boletería"
    app_env: str = "development"
    database_url: str = "postgresql+asyncpg://tava:tava_secret@localhost:5432/tava_db"
    jwt_secret_key: str = "dev-secret-change-in-production-min-32-chars"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    cors_origins: str = "http://localhost:4200"
    rate_limit_per_minute: int = 60
    captcha_secret_key: str = ""
    frontend_url: str = "http://localhost:4200"
    uploads_dir: str = "uploads"
    """URL pública del API sin /api/v1 (p. ej. https://tava-api-1.onrender.com)."""
    api_public_base_url: str = ""
    # Cloudinary — almacenamiento persistente (imágenes/videos no se pierden en Render)
    cloudinary_cloud_name: str = ""
    cloudinary_api_key: str = ""
    cloudinary_api_secret: str = ""
    """Preset de subida sin firma (más fácil en Render). Crear en Cloudinary → Settings → Upload."""
    cloudinary_upload_preset: str = ""
    # Correo (opcional: sin SMTP solo se registra en logs en desarrollo)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    email_from: str = "TAVA Teatro <no-reply@tavateatro.com>"
    email_verification_expire_hours: int = 48
    password_reset_expire_hours: int = 2
    privacy_policy_version: str = "1.0-2026"
    resend_api_key: str = ""  # https://resend.com (API HTTPS, funciona en Render)
    brevo_api_key: str = ""  # https://www.brevo.com — recomendado en Render (gratis ~300/día)
    """Correo verificado en Brevo (Senders). Debe coincidir con un remitente validado en el panel."""
    brevo_sender_email: str = ""
    brevo_sender_name: str = "TAVA Teatro"
    email_enable_smtp: bool = False  # True solo en local; Render bloquea puertos 25/465/587

    @model_validator(mode="after")
    def _apply_production_defaults(self) -> "Settings":
        if self.app_env.strip().lower() == "production":
            fu = self.frontend_url.strip().rstrip("/")
            if not fu or fu.startswith("http://localhost"):
                self.frontend_url = PRODUCTION_FRONTEND_URL
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        """Acepta orígenes separados por coma o punto y coma (sin barra final)."""
        raw = self.cors_origins.replace(";", ",")
        origins: list[str] = []
        for part in raw.split(","):
            origin = part.strip().rstrip("/")
            if origin and origin not in origins:
                origins.append(origin)
        return origins


@lru_cache
def get_settings() -> Settings:
    return Settings()
