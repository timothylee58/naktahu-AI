"""Public Knowledge API — API-key authenticated JSON/SSE endpoints."""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import Annotated, Any, AsyncGenerator, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, Field, field_validator

from app.middleware.sanitise import sanitise_query
from app.routers.query import _run_pipeline, _sse
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
        try:
            result = await _run_pipeline(clean, session_id, ctx.user_id)
            for token in result["tokens"]:
                yield _sse("token", {"text": token})
            final_state = result["final_state"]
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
            domain=str(result.get("final_state", {}).get("domain") or "general"),
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
    """Swagger UI for the public Knowledge API."""
    html = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>NakTahu Knowledge API</title>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/swagger-ui/5.11.0/swagger-ui.min.css" />
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/swagger-ui/5.11.0/swagger-ui-bundle.min.js"></script>
  <script>
    SwaggerUIBundle({
      url: '/api/v1/public/openapi.json',
      dom_id: '#swagger-ui',
      presets: [SwaggerUIBundle.presets.apis],
      layout: 'BaseLayout'
    });
  </script>
</body>
</html>"""
    return HTMLResponse(content=html)
