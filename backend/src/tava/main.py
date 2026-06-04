import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

from tava.config import get_settings
from tava.infrastructure.persistence.database import init_db
from tava.presentation.api.error_handlers import register_exception_handlers
from tava.presentation.api.routers import auth, dashboard, events, loyalty, marketing, tickets, validation, venues

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("tava")

settings = get_settings()


def _rate_limit_key(request: Request) -> str:
    if request.method == "OPTIONS":
        return "options-exempt"
    return get_remote_address(request) or "anonymous"


limiter = Limiter(key_func=_rate_limit_key)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        await init_db()
        logger.info("Base de datos inicializada")
    except Exception:
        logger.exception("init_db falló — la API arrancará pero operaciones de DB pueden fallar")
    yield


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description=(
        "API oficial del ecosistema TAVA (@tavateatro) — gestión de eventos, boletería, "
        "validación QR, fidelización y reportería."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

register_exception_handlers(app)

app.state.limiter = limiter

# CORS primero (último en add_middleware = más externo)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(events.router, prefix="/api/v1")
app.include_router(venues.router, prefix="/api/v1")
app.include_router(tickets.router, prefix="/api/v1")
app.include_router(validation.router, prefix="/api/v1")
app.include_router(loyalty.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")
app.include_router(marketing.router, prefix="/api/v1")


@app.get("/health")
@limiter.exempt
async def health():
    return {"status": "ok", "service": "tava-api"}


@app.get("/health/db")
@limiter.exempt
async def health_db():
    from sqlalchemy import text

    from tava.infrastructure.persistence.database import engine

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as exc:
        logger.exception("health/db falló")
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "database": "disconnected",
                "error_type": "system",
                "message": str(exc),
            },
        )
