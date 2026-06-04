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

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
