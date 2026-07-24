"""Prometheus /metrics endpoint — scraped by an external Prometheus server.

Bare /metrics at root (no /api/v1 prefix), matching default Prometheus
scrape-config expectations (metrics_path: /metrics). Auth is a static bearer
token, not the JWT-based get_current_user used elsewhere — a Prometheus
scraper can't do an interactive login flow, and this endpoint isn't
user-facing.
"""
from __future__ import annotations

import secrets

from fastapi import APIRouter, HTTPException, Request, Response, status

from app.core.prometheus_metrics import CONTENT_TYPE_LATEST, render_metrics
from core.config import settings

router = APIRouter(tags=["metrics"])


def verify_metrics_token(request: Request) -> None:
    # Fail closed: an unconfigured token means the endpoint always 401s,
    # never falls open just because nobody set the env var.
    if not settings.metrics_auth_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Metrics endpoint not configured")

    auth_header = request.headers.get("Authorization", "")
    scheme, _, token = auth_header.partition(" ")
    if scheme.lower() != "bearer" or not secrets.compare_digest(token, settings.metrics_auth_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing metrics token")


@router.get("/metrics")
async def metrics(request: Request) -> Response:
    verify_metrics_token(request)
    return Response(content=render_metrics(), media_type=CONTENT_TYPE_LATEST)
