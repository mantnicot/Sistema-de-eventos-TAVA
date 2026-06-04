from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi import Limiter
from slowapi.util import get_remote_address

from tava.config import get_settings
from tava.infrastructure.persistence.database import init_db
from tava.presentation.api.routers import auth, dashboard, events, loyalty, marketing, tickets, validation, venues

settings = get_settings()
limiter = Limiter(key_func=get_remote_address, default_limits=[f"{settings.rate_limit_per_minute}/minute"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
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

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
async def health():
    return {"status": "ok", "service": "tava-api"}
