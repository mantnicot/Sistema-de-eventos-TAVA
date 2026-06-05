from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    # Correo (opcional: sin SMTP solo se registra en logs en desarrollo)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    email_from: str = "TAVA Teatro <no-reply@tavateatro.com>"
    email_verification_expire_hours: int = 48
    resend_api_key: str = ""  # opcional: https://resend.com si Gmail SMTP falla en Render

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
