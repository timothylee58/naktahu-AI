"""FastAPI application entry point."""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.telemetry import configure_telemetry
from app.core.weave_tracing import init_weave
from app.middleware.request_id import RequestIDMiddleware
from app.routers.health import router as health_router
from app.routers.query import router as query_router
from app.routers.session import router as session_router

# Initialise Sentry + structlog before the app object is created so that
# any import-time errors are captured too.
configure_telemetry()

log = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI):  # type: ignore[type-arg]
    init_weave()
    log.info("startup", version=application.version)
    yield
    log.info("shutdown")


app = FastAPI(
    title="NakTahu AI API",
    version="0.1.0",
    description="Malaysian bilingual AI answer engine — FastAPI backend",
    lifespan=lifespan,
)

# ── Middleware (outermost → innermost) ──────────────────────────────────────

# 1. CORS
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

# 2. Request-ID (binds structlog context + echoes header)
app.add_middleware(RequestIDMiddleware)

# ── Routers ─────────────────────────────────────────────────────────────────
app.include_router(health_router)
app.include_router(query_router)
app.include_router(session_router)
