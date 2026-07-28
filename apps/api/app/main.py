"""FastAPI application entry point."""
from __future__ import annotations

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

from app.agents.checkpointer import init_checkpointer
from app.core.telemetry import configure_telemetry
from app.core.weave_tracing import init_weave
from app.middleware.request_id import RequestIDMiddleware
from app.routers.agents import router as agents_router
from app.routers.eligibility import router as eligibility_router
from app.routers.investor import router as investor_router
from app.routers.health import router as health_router
from app.routers.query import router as query_router
from app.routers.session import router as session_router
from app.routers.transcribe import router as transcribe_router
from core.config import settings
from middleware.prometheus_middleware import PrometheusMiddleware
from middleware.rate_limit import anonymous_limiter
from middleware.security_headers import SecurityHeadersMiddleware
from middleware.user_context import UserContextMiddleware
from routers import billing, feedback, history, parliament, share
from routers.api_v1_public import router as public_api_router
from routers.developer import router as developer_router
from app.routers.metrics import router as metrics_router
from app.routers.observability import router as observability_router
from app.orchestration.adapters import ALL_ADAPTERS
from app.orchestration.context_bus import ContextBus
from app.orchestration.registry import load_enhanced_registry, register_adapter
from app.routers.orchestrate import router as orchestrate_router
from app.routers.orchestration import router as orchestration_router
from scripts.setup_agent_infra import ensure_storage_bucket
from services.agent_registry import load_agent_registry

configure_telemetry()
log = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI):  # type: ignore[type-arg]
    init_weave()

    application.state.redis = redis_ai.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
    )
    try:
        await application.state.redis.ping()
        log.info("redis_status", ok=True)
    except Exception as exc:
        log.warning("redis_status", ok=False, error=str(exc))
        application.state.redis = None

    try:
        sb = create_client(settings.supabase_url, settings.supabase_service_key)
        sb.table("user_sessions").select("user_id").limit(1).execute()
        application.state.supabase = sb
        log.info("supabase_status", ok=True)
    except Exception as exc:
        log.warning("supabase_status", ok=False, error=str(exc))
        application.state.supabase = None

    application.state.checkpointer = await init_checkpointer()
    ensure_storage_bucket(application.state.supabase)
    load_agent_registry(application.state.supabase)

    # ── Observability: cleanup abandoned sessions on startup ───────────────
    from app.orchestration.session_manager import cleanup_abandoned_sessions
    if application.state.supabase:
        cleanup_result = await cleanup_abandoned_sessions(application.state.supabase)
        if cleanup_result.deleted_count > 0:
            log.info("startup_session_cleanup", deleted=cleanup_result.deleted_count)
    # ── Orchestration layer bootstrap ──────────────────────────────────────
    load_enhanced_registry(application.state.supabase)
    application.state.context_bus = ContextBus(application.state.redis)
    for adapter_cls in ALL_ADAPTERS:
        register_adapter(adapter_cls())
    log.info("orchestration_ready", adapters=len(ALL_ADAPTERS))

    log.info("startup", version=application.version)
    yield

    if application.state.redis:
        await application.state.redis.aclose()
    log.info("shutdown")


app = FastAPI(
    title="NakTahu AI API",
    version="0.1.0",
    description="Malaysian bilingual AI answer engine — FastAPI backend",
    lifespan=lifespan,
)

_cors_origins_raw = os.environ.get(
    "CORS_ORIGINS",
    "http://localhost:3000,https://naktahu.netlify.app",
)
_cors_origins = [o.strip() for o in _cors_origins_raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RequestIDMiddleware)

app.state.limiter = anonymous_limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(UserContextMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(PrometheusMiddleware)

app.include_router(health_router)
app.include_router(query_router)
app.include_router(session_router)
app.include_router(transcribe_router)
app.include_router(agents_router)
app.include_router(history.router)
app.include_router(feedback.router)
app.include_router(billing.router)
app.include_router(share.router)
app.include_router(parliament.router)
app.include_router(eligibility_router)
app.include_router(investor_router)
app.include_router(public_api_router)
app.include_router(developer_router)
app.include_router(metrics_router)
app.include_router(observability_router)
app.include_router(orchestration_router)
app.include_router(orchestrate_router)
