"""Shared agent tools: RAG query, PDF generation, email notification."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx
import structlog

from app.services.llm_client import ILMU_EMBEDDING_MODEL, ilmu_client, openai_client, OPENAI_EMBEDDING_MODEL
from app.services.vector_store import ChunkResult, hybrid_search

log = structlog.get_logger(__name__)


async def _embed(query: str) -> list[float]:
    try:
        resp = await ilmu_client.embeddings.create(input=query, model=ILMU_EMBEDDING_MODEL)
        return resp.data[0].embedding
    except Exception as exc:
        if openai_client is None:
            raise RuntimeError("No embedding provider available") from exc
        resp = await openai_client.embeddings.create(input=query, model=OPENAI_EMBEDDING_MODEL)
        return resp.data[0].embedding


async def query_rag(
    query: str,
    domain: str,
    *,
    language: str = "bm",
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """Hybrid-search a domain and return serialisable chunk dicts."""
    embedding = await _embed(query)
    chunks: list[ChunkResult] = await hybrid_search(
        query_embedding=embedding,
        query_text=query,
        domain=domain,
        language=language,
        top_k=top_k,
    )
    return [
        {
            "id": c.id,
            "content": c.content,
            "source_title": c.source_title,
            "source_url": c.source_url,
            "ministry": c.ministry,
            "similarity": c.similarity,
        }
        for c in chunks
    ]


def _chunks_to_findings(chunks: list[dict[str, Any]], domain: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for c in chunks[:3]:
        findings.append({
            "domain": domain,
            "summary": c.get("content", "")[:400],
            "source_title": c.get("source_title", ""),
            "source_url": c.get("source_url", ""),
        })
    return findings


async def query_rag_findings(
    query: str,
    domain: str,
    language: str = "bm",
) -> list[dict[str, Any]]:
    chunks = await query_rag(query, domain, language=language)
    return _chunks_to_findings(chunks, domain)


async def generate_pdf(
    html: str,
    *,
    user_id: str,
    agent_type: str = "compliance-drafter",
    supabase_client: Any = None,
) -> tuple[str, str, str]:
    """Render HTML to PDF, upload to Supabase Storage. Returns (path, signed_url, expires_at)."""
    pdf_bytes: bytes
    try:
        from weasyprint import HTML  # type: ignore[import-untyped]

        pdf_bytes = HTML(string=html).write_pdf()
    except Exception as exc:
        log.warning("weasyprint_unavailable", error=str(exc))
        pdf_bytes = html.encode("utf-8")

    storage_path = f"agents/{agent_type}/{user_id}/{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}.pdf"
    bucket = os.environ.get("SUPABASE_STORAGE_BUCKET", "generated-documents")

    if not supabase_client:
        return storage_path, "", ""

    try:
        supabase_client.storage.from_(bucket).upload(
            storage_path,
            pdf_bytes,
            {"content-type": "application/pdf", "upsert": "true"},
        )
        expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
        signed = supabase_client.storage.from_(bucket).create_signed_url(
            storage_path,
            86_400,
        )
        url = signed.get("signedURL") or signed.get("signedUrl") or ""
        return storage_path, url, expires_at.isoformat()
    except Exception as exc:
        log.warning("pdf_upload_failed", error=str(exc))
        return storage_path, "", ""


async def send_email(
    *,
    to: str,
    subject: str,
    html_body: str,
) -> bool:
    """Send via Resend API. Returns False when not configured."""
    api_key = os.environ.get("RESEND_API_KEY", "").strip()
    from_addr = os.environ.get("RESEND_FROM_EMAIL", "NakTahu <noreply@naktahu.ai>").strip()
    if not api_key or not to:
        log.info("send_email_skipped", reason="not_configured")
        return False

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"from": from_addr, "to": [to], "subject": subject, "html": html_body},
        )
        if resp.status_code >= 400:
            log.warning("send_email_failed", status=resp.status_code)
            return False
    return True
