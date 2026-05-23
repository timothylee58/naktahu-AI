"""Sentry and structlog initialisation.

Call configure_telemetry() once at application startup — it is idempotent.
"""
from __future__ import annotations

import logging
import os
import sys

import sentry_sdk
import structlog
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration


def configure_telemetry() -> None:
    _configure_structlog()
    _configure_sentry()


# ---------------------------------------------------------------------------
# structlog
# ---------------------------------------------------------------------------

def _configure_structlog() -> None:
    env = os.environ.get("ENV", "development")
    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if env == "production":
        processors = shared_processors + [structlog.processors.JSONRenderer()]
    else:
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty())
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.BoundLogger,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Redirect stdlib logging into structlog so uvicorn access logs are captured
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.INFO,
    )


# ---------------------------------------------------------------------------
# Sentry
# ---------------------------------------------------------------------------

def _configure_sentry() -> None:
    dsn = os.environ.get("SENTRY_DSN", "")
    if not dsn:
        return  # skip silently in local dev without a DSN

    sentry_sdk.init(
        dsn=dsn,
        environment=os.environ.get("ENV", "development"),
        release=os.environ.get("RELEASE", "naktahu-api@0.1.0"),
        traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.2")),
        integrations=[
            StarletteIntegration(transaction_style="url"),
            FastApiIntegration(transaction_style="url"),
        ],
        # Strip PII from breadcrumbs
        send_default_pii=False,
    )
