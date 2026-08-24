import os
from contextlib import asynccontextmanager

import redis.asyncio as redis_ai
import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from supabase import create_client

from app.core.telemetry import configure_telemetry
from core.config import settings
from middleware.prometheus_middleware import PrometheusMiddleware
from middleware.rate_limit import anonymous_limiter
from middleware.security_headers import SecurityHeadersMiddleware
from middleware.user_context import UserContextMiddleware
from routes import query as rag_query  # noqa: F401 — lazy RAG imports inside
from app.routers.agents import router as agents_router
from app.routers.eligibility import router as eligibility_router
from app.routers.investor import router as investor_router
from routers import billing, calendar as calendar_router, feedback, history, parliament, property_listings, query, referrals, share, warung_watch
from routers.developer import router as developer_router
from routers.metrics import router as metrics_router
from routers.observability import router as observability_router
from routers.orchestrate import router as orchestrate_router
from routers.orchestration import router as orchestration_router

# Trap #1 (two mains): app/main.py has called this since Sentry was added,
# root main.py never did — so whichever tree Railway actually serves
# determined whether backend errors reached Sentry at all. configure_telemetry
# is idempotent and no-ops without SENTRY_DSN, so calling it in both is safe.
configure_telemetry()

structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ],
)
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.redis = redis_ai.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
    )
    try:
        await app.state.redis.ping()
        logger.info("redis_status", ok=True, detail="ping successful")
    except Exception as exc:
        logger.error("redis_status", ok=False, error=str(exc))
        raise

    try:
        sb = create_client(settings.supabase_url, settings.supabase_service_key)
        sb.table("user_sessions").select("user_id").limit(1).execute()
        app.state.supabase = sb
        logger.info("supabase_status", ok=True, detail="client ready")
    except Exception as exc:
        logger.error("supabase_status", ok=False, error=str(exc))
        app.state.supabase = None  # degraded mode — history/session features disabled

    yield

    await app.state.redis.aclose()


app = FastAPI(title="Naktahu API", lifespan=lifespan)

_raw_origins = os.environ.get(
    "CORS_ORIGINS",
    "http://localhost:3000,https://naktahu.netlify.app",
)
_allow_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.state.limiter = anonymous_limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(SlowAPIMiddleware)
app.add_middleware(UserContextMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(PrometheusMiddleware)

app.include_router(query.router)
app.include_router(history.router)
app.include_router(feedback.router)
app.include_router(billing.router)
app.include_router(calendar_router.router)
app.include_router(referrals.router)
app.include_router(share.router)
app.include_router(parliament.router)
app.include_router(property_listings.router)
app.include_router(warung_watch.router)
app.include_router(agents_router)
app.include_router(eligibility_router)
app.include_router(investor_router)
app.include_router(developer_router)
app.include_router(metrics_router)
app.include_router(observability_router)
app.include_router(orchestration_router)
app.include_router(orchestrate_router)
app.include_router(rag_query.router, prefix="/rag")


@app.get("/health")
async def health():
    return {"status": "ok"}
