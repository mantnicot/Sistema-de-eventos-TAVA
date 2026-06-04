from collections.abc import AsyncGenerator
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from tava.config import get_settings
from tava.infrastructure.persistence.models import Base

# Parámetros de libpq que asyncpg no acepta (p. ej. URLs de Neon)
_ASYNCPG_STRIP_QUERY_PARAMS = frozenset({"sslmode", "channel_binding"})


def _prepare_asyncpg_url(database_url: str) -> tuple[str, dict]:
    """Limpia la URL y define SSL para hosts remotos (Neon, Render, etc.)."""
    parsed = urlparse(database_url)
    query = parse_qs(parsed.query)
    ssl_required = query.get("sslmode", [""])[0] in ("require", "verify-ca", "verify-full")

    for key in _ASYNCPG_STRIP_QUERY_PARAMS:
        query.pop(key, None)

    flat_query = {k: values[0] for k, values in query.items() if values}
    clean_query = urlencode(flat_query)
    clean_url = urlunparse(parsed._replace(query=clean_query))

    host = (parsed.hostname or "").lower()
    local_hosts = {"localhost", "127.0.0.1", "postgres"}
    use_ssl = ssl_required or (bool(host) and host not in local_hosts)

    connect_args: dict = {"ssl": True} if use_ssl else {}
    return clean_url, connect_args


settings = get_settings()
_db_url, _connect_args = _prepare_asyncpg_url(settings.database_url)

engine = create_async_engine(
    _db_url,
    echo=settings.app_env == "development",
    connect_args=_connect_args,
)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
