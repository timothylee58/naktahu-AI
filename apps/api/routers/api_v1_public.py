"""Public Knowledge API — API-key authenticated JSON/SSE endpoints."""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import Annotated, Any, AsyncGenerator, Optional

import structlog
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, Field, field_validator

from app.middleware.sanitise import sanitise_query
from app.routers.query import _run_pipeline, _sse, _stream_pipeline
from core.config import settings
from middleware.api_key_auth import get_api_key_context
from middleware.api_key_rate_limit import enforce_api_key_rate_limit, enforce_multi_rate_limit, enforce_sse_rate_limit
from services.api_key_service import ApiKeyContext, increment_usage, log_api_key_event

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/public", tags=["public-api"])

PUBLIC_DOMAINS = [
    "government",
    "education",
    "legal",
    "finance",
    "healthcare",
    "epf",
    "tax",
    "business",
    "immigration",
    "culture",
]


class PublicQueryRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=1000)
    language: Optional[str] = None
    domain: Optional[str] = None
    session_id: Optional[str] = Field(default=None, max_length=128)

    @field_validator("session_id")
    @classmethod
    def session_id_alphanumeric(cls, v: Optional[str]) -> Optional[str]:
        import re

        if v is not None and not re.match(r"^[\w\-]+$", v):
            raise ValueError("session_id must contain only alphanumeric, hyphens, or underscores")
        return v


class PublicMultiQueryRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=1000)
    domains: list[str] = Field(..., min_length=2, max_length=6)
    language: Optional[str] = None

    @field_validator("domains")
    @classmethod
    def validate_domains(cls, v: list[str]) -> list[str]:
        normalised = [d.strip().lower() for d in v]
        invalid = [d for d in normalised if d not in PUBLIC_DOMAINS]
        if invalid:
            raise ValueError(f"Unknown domains: {', '.join(invalid)}")
        return normalised


class CitationOut(BaseModel):
    title: str
    ministry: str
    url: str
    confidence: float = 0.0


class PublicQueryResponse(BaseModel):
    answer: str
    citations: list[CitationOut]
    confidence: float
    domain: str
    language: str
    latency_ms: int


class DomainInfo(BaseModel):
    domain: str
    chunk_count: int


class DomainsResponse(BaseModel):
    domains: list[DomainInfo]


class MultiQueryResult(BaseModel):
    domain: str
    answer: str
    citations: list[CitationOut]
    confidence: float
    language: str
    latency_ms: int


class PublicMultiQueryResponse(BaseModel):
    results: list[MultiQueryResult]
    total_latency_ms: int


def _citations_out(raw: list[Any]) -> list[CitationOut]:
    out: list[CitationOut] = []
    for c in raw:
        if not isinstance(c, dict):
            continue
        out.append(
            CitationOut(
                title=str(c.get("title") or ""),
                ministry=str(c.get("ministry") or ""),
                url=str(c.get("url") or ""),
                confidence=float(c.get("confidence") or 0.0),
            )
        )
    return out


async def _execute_query(
    *,
    query: str,
    session_id: str,
    domain: Optional[str],
    ctx: ApiKeyContext,
    request: Request,
    endpoint: str,
) -> tuple[dict[str, Any], int]:
    t0 = time.monotonic()
    preset_domain = domain if domain in PUBLIC_DOMAINS else None

    result = await _run_pipeline(query, session_id, ctx.user_id, domain=preset_domain)
    tokens = result["tokens"]
    final_state = result["final_state"]
    answer = "".join(tokens) or str(final_state.get("streaming_token_buffer") or "")
    latency_ms = int(result.get("metrics", {}).get("latency_ms") or round((time.monotonic() - t0) * 1000))

    redis_client = getattr(request.app.state, "redis", None)
    supabase = getattr(request.app.state, "supabase", None)
    await increment_usage(redis_client, supabase, ctx.key_id)
    await log_api_key_event(
        supabase,
        key_id=ctx.key_id,
        endpoint=endpoint,
        domain=str(final_state.get("domain") or domain or "general"),
        response_ms=latency_ms,
    )

    return {
        "answer": answer,
        "citations": list(final_state.get("citations") or []),
        "confidence": float(final_state.get("confidence_score") or 0.0),
        "domain": str(final_state.get("domain") or domain or "government"),
        "language": str(final_state.get("language") or "en"),
        "latency_ms": latency_ms,
    }, latency_ms


def _attach_rate_headers(request: Request, response: Response) -> None:
    headers = getattr(request.state, "rate_limit_headers", None)
    if isinstance(headers, dict):
        for key, value in headers.items():
            response.headers[key] = value


@router.post("/query", response_model=PublicQueryResponse)
async def public_query(
    body: PublicQueryRequest,
    request: Request,
    response: Response,
    ctx: Annotated[ApiKeyContext, Depends(enforce_api_key_rate_limit)],
) -> PublicQueryResponse:
    clean = sanitise_query(body.query)
    session_id = body.session_id or str(uuid.uuid4())
    payload, _ = await _execute_query(
        query=clean,
        session_id=session_id,
        domain=body.domain,
        ctx=ctx,
        request=request,
        endpoint="/api/v1/public/query",
    )
    _attach_rate_headers(request, response)
    return PublicQueryResponse(
        answer=payload["answer"],
        citations=_citations_out(payload["citations"]),
        confidence=payload["confidence"],
        domain=payload["domain"],
        language=payload["language"],
        latency_ms=payload["latency_ms"],
    )


@router.post("/query/stream")
async def public_query_stream(
    body: PublicQueryRequest,
    request: Request,
    ctx: Annotated[ApiKeyContext, Depends(enforce_sse_rate_limit)],
) -> StreamingResponse:
    clean = sanitise_query(body.query)
    session_id = body.session_id or str(uuid.uuid4())

    async def _gen() -> AsyncGenerator[str, None]:
        t0 = time.monotonic()
        final_state: dict = {}
        try:
            async for kind, payload in _stream_pipeline(clean, session_id, ctx.user_id):
                if kind == "token":
                    yield _sse("token", {"text": payload})
                else:  # kind == "result"
                    final_state = payload["final_state"]
            for citation in final_state.get("citations", []):
                yield _sse("citation", dict(citation))
            yield _sse(
                "metadata",
                {
                    "confidence": final_state.get("confidence_score", 0.0),
                    "domain": final_state.get("domain", "government"),
                    "language": final_state.get("language", "en"),
                },
            )
            yield _sse("done", {})
        except Exception as exc:
            log.error("public_stream_error", error=str(exc))
            yield _sse("error", {"message": "An error occurred. Please try again."})
            return

        latency_ms = int(round((time.monotonic() - t0) * 1000))
        redis_client = getattr(request.app.state, "redis", None)
        supabase = getattr(request.app.state, "supabase", None)
        await increment_usage(redis_client, supabase, ctx.key_id)
        await log_api_key_event(
            supabase,
            key_id=ctx.key_id,
            endpoint="/api/v1/public/query/stream",
            domain=str(final_state.get("domain") or "general"),
            response_ms=latency_ms,
        )

    return StreamingResponse(
        _gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/query/multi", response_model=PublicMultiQueryResponse)
async def public_query_multi(
    body: PublicMultiQueryRequest,
    request: Request,
    ctx: Annotated[ApiKeyContext, Depends(enforce_multi_rate_limit)],
) -> PublicMultiQueryResponse:
    clean = sanitise_query(body.query)
    t0 = time.monotonic()

    async def _one(domain: str) -> MultiQueryResult:
        session_id = str(uuid.uuid4())
        payload, latency = await _execute_query(
            query=clean,
            session_id=session_id,
            domain=domain,
            ctx=ctx,
            request=request,
            endpoint="/api/v1/public/query/multi",
        )
        return MultiQueryResult(
            domain=domain,
            answer=payload["answer"],
            citations=_citations_out(payload["citations"]),
            confidence=payload["confidence"],
            language=payload["language"],
            latency_ms=latency,
        )

    results = await asyncio.gather(*[_one(d) for d in body.domains])
    return PublicMultiQueryResponse(
        results=list(results),
        total_latency_ms=int(round((time.monotonic() - t0) * 1000)),
    )


class PublicMultiQueryResponse(BaseModel):
    results: list[MultiQueryResult]
    total_latency_ms: int


class PublicConfigResponse(BaseModel):
    plan: str
    widget: bool
    white_label: bool
    sse: bool
    multi: bool


@router.get("/config", response_model=PublicConfigResponse)
async def public_config(
    ctx: Annotated[ApiKeyContext, Depends(get_api_key_context)],
) -> PublicConfigResponse:
    return PublicConfigResponse(
        plan=ctx.plan,
        widget=ctx.widget,
        white_label=ctx.white_label,
        sse=ctx.sse,
        multi=ctx.multi,
    )


@router.get("/domains", response_model=DomainsResponse)
async def list_domains(
    request: Request,
    ctx: Annotated[ApiKeyContext, Depends(get_api_key_context)],
) -> DomainsResponse:
    supabase = getattr(request.app.state, "supabase", None)
    counts: dict[str, int] = {d: 0 for d in PUBLIC_DOMAINS}

    if supabase is not None:

        def _count() -> dict[str, int]:
            out = dict(counts)
            for domain in PUBLIC_DOMAINS:
                res = (
                    supabase.table("document_chunks")
                    .select("id", count="exact")
                    .eq("domain", domain)
                    .execute()
                )
                out[domain] = int(res.count or 0)
            return out

        counts = await asyncio.to_thread(_count)

    return DomainsResponse(
        domains=[DomainInfo(domain=d, chunk_count=counts.get(d, 0)) for d in PUBLIC_DOMAINS]
    )


@router.get("/openapi.json", include_in_schema=False)
async def public_openapi(request: Request) -> JSONResponse:
    """OpenAPI spec for the public Knowledge API."""
    from app.main import app as root_app

    schema = root_app.openapi()
    public_paths = {k: v for k, v in schema.get("paths", {}).items() if k.startswith("/api/v1/public")}
    schema["paths"] = public_paths
    schema["info"] = {
        "title": "NakTahu Knowledge API",
        "version": "1.0.0",
        "description": "Malaysian bilingual knowledge API with citations. Authenticate via X-NakTahu-Key header.",
    }
    schema["components"] = schema.get("components", {})
    schema["components"]["securitySchemes"] = {
        "ApiKeyAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-NakTahu-Key",
        }
    }
    return JSONResponse(schema)


@router.get("/docs", include_in_schema=False, response_class=HTMLResponse)
async def public_docs() -> HTMLResponse:
    """Branded Swagger UI for the public Knowledge API.

    Stock Swagger UI (the previous version of this page) has no NakTahu
    identity, no link back to where a key actually comes from
    (/developer), and its default green/blue "Try it out" chrome clashes
    with the brand blue used everywhere else in the app. This wraps the
    same SwaggerUIBundle in a branded header + CSS override — same spec
    (/api/v1/public/openapi.json), same Swagger UI version pinned from
    the same CDN, purely presentational.

    This page is served from the API's own origin (Railway), not the web
    app's (Netlify) — "/developer" and "/" would 404 here if left as
    relative links, so the brand-header nav uses settings.frontend_url
    explicitly."""
    frontend = settings.frontend_url.rstrip("/")
    # Plain string + placeholder .replace(), not an f-string — the CSS
    # block below is full of literal { } which an f-string would try to
    # parse as interpolations.
    html = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>NakTahu Knowledge API — Docs</title>
  <link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Crect width='24' height='24' rx='6' fill='%233b5bff'/%3E%3C/svg%3E" />
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/swagger-ui/5.11.0/swagger-ui.min.css" />
  <style>
    :root {
      --nk-blue: #3b5bff;
      --nk-blue-dark: #2540c9;
      --nk-ink: #12151c;
    }
    html, body { margin: 0; background: #f8f9fc; }
    /* Brand header — replaces Swagger UI's own topbar entirely (hidden below) */
    .nk-docs-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      flex-wrap: wrap;
      padding: 16px 32px;
      background: linear-gradient(150deg, var(--nk-blue), var(--nk-blue-dark));
      color: #fff;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    }
    .nk-docs-brand { display: flex; align-items: center; gap: 10px; text-decoration: none; color: #fff; }
    .nk-docs-mark { width: 24px; height: 20px; border-radius: 46% 46% 46% 4px / 50% 50% 50% 4px; background: rgba(255,255,255,0.95); flex-shrink: 0; }
    .nk-docs-title { font-size: 15px; font-weight: 700; letter-spacing: -0.01em; }
    .nk-docs-subtitle { font-size: 12px; color: rgba(255,255,255,0.75); font-weight: 500; }
    .nk-docs-links { display: flex; align-items: center; gap: 10px; font-size: 13px; font-weight: 600; }
    .nk-docs-links a {
      color: #fff;
      text-decoration: none;
      padding: 7px 14px;
      border-radius: 999px;
      border: 1px solid rgba(255,255,255,0.35);
      transition: background 0.15s ease, border-color 0.15s ease;
      white-space: nowrap;
    }
    .nk-docs-links a:hover { background: rgba(255,255,255,0.12); border-color: rgba(255,255,255,0.6); }
    .nk-docs-links a.nk-docs-cta { background: #fff; color: var(--nk-blue-dark); border-color: #fff; }
    .nk-docs-links a.nk-docs-cta:hover { background: rgba(255,255,255,0.9); }

    /* Swagger UI's own topbar is redundant with the header above */
    .swagger-ui .topbar { display: none; }
    /* Rebrand Swagger UI's default green/blue accents to the site's brand blue */
    .swagger-ui .btn.authorize,
    .swagger-ui .btn.authorize svg { color: var(--nk-blue); border-color: var(--nk-blue); }
    .swagger-ui .btn.execute { background: var(--nk-blue); border-color: var(--nk-blue); }
    .swagger-ui .btn.execute:hover { background: var(--nk-blue-dark); border-color: var(--nk-blue-dark); }
    .swagger-ui .opblock.opblock-post { border-color: var(--nk-blue); background: rgba(59,91,255,0.04); }
    .swagger-ui .opblock.opblock-post .opblock-summary-method { background: var(--nk-blue); }
    .swagger-ui .opblock-tag { border-bottom-color: #e4e4e7; }
    .swagger-ui a.nostyle, .swagger-ui .info a { color: var(--nk-blue); }
    .swagger-ui .scheme-container { background: transparent; box-shadow: none; }
    .swagger-ui .info { margin: 24px 0; }
    #swagger-ui { max-width: 1100px; margin: 0 auto; padding: 0 16px; }
  </style>
</head>
<body>
  <header class="nk-docs-header">
    <a href="__FRONTEND__/" class="nk-docs-brand">
      <span class="nk-docs-mark" aria-hidden="true"></span>
      <span>
        <div class="nk-docs-title">NakTahu Knowledge API</div>
        <div class="nk-docs-subtitle">Malaysian bilingual answers, with citations</div>
      </span>
    </a>
    <nav class="nk-docs-links">
      <a href="__FRONTEND__/developer">Get an API key</a>
      <a href="/api/v1/public/openapi.json">OpenAPI JSON</a>
      <a href="__FRONTEND__/developer" class="nk-docs-cta">Dashboard →</a>
    </nav>
  </header>
  <div id="swagger-ui"></div>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/swagger-ui/5.11.0/swagger-ui-bundle.min.js"></script>
  <script>
    SwaggerUIBundle({
      url: '/api/v1/public/openapi.json',
      dom_id: '#swagger-ui',
      presets: [SwaggerUIBundle.presets.apis],
      layout: 'BaseLayout',
      docExpansion: 'list',
      filter: true,
      deepLinking: true,
      persistAuthorization: true,
      tryItOutEnabled: true
    });
  </script>
</body>
</html>"""
    return HTMLResponse(content=html.replace("__FRONTEND__", frontend))
