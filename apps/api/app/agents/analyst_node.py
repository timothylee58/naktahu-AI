"""analyst_node — score citations, set confidence, flag clarification."""
from __future__ import annotations

import re
from datetime import date

import structlog
import weave

from app.models.state import AgentState, Citation
from app.services.vector_store import ChunkResult

log = structlog.get_logger(__name__)

_GOV_DOMAIN_RE = re.compile(
    r"https?://(?:[\w\-]+\.)*(?:gov\.my|edu\.my|org\.my)(?:/|$)",
    re.IGNORECASE,
)

_CLARIFICATION_THRESHOLD = 0.4
_STALE_DAYS = 90
_MIN_SUPPORTING_CHUNK_SCORE = 0.3
_MIN_SUPPORTING_CHUNKS = 2


def _is_stale(chunk: ChunkResult) -> bool:
    if not chunk.expiry_aware or not chunk.source_date:
        return False
    try:
        source_dt = date.fromisoformat(chunk.source_date)
        return (date.today() - source_dt).days > _STALE_DAYS
    except ValueError:
        return False


def _score_chunk(chunk: ChunkResult, query: str) -> float:
    score = 0.0

    # URL is a real Malaysian government / education domain (+0.3)
    if chunk.source_url and _GOV_DOMAIN_RE.match(chunk.source_url):
        score += 0.3

    # Non-empty source title (+0.2)
    if chunk.source_title and chunk.source_title.strip():
        score += 0.2

    # Keyword overlap between chunk content and query (+0.5 max)
    query_tokens = set(re.findall(r"\w+", query.lower()))
    content_tokens = set(re.findall(r"\w+", chunk.content.lower()))
    if query_tokens:
        overlap = len(query_tokens & content_tokens) / len(query_tokens)
        score += min(overlap, 1.0) * 0.5

    return round(min(score, 1.0), 4)


@weave.op()
async def analyst_node(state: AgentState) -> dict:
    """Score retrieved chunks, select top 3 citations, compute confidence."""
    query = state.get("query", "")
    chunks: list[ChunkResult] = state.get("retrieved_chunks", [])

    if not chunks:
        log.warning("analyst_no_chunks")
        return {
            "citations": [],
            "confidence_score": 0.0,
            "needs_clarification": True,
        }

    scored: list[tuple[float, ChunkResult]] = [
        (_score_chunk(chunk, query), chunk) for chunk in chunks
    ]
    scored.sort(key=lambda t: t[0], reverse=True)

    top3 = scored[:3]
    confidence = sum(s for s, _ in top3) / len(top3)

    citations: list[Citation] = [
        Citation(
            title=chunk.source_title,
            ministry=chunk.ministry,
            url=chunk.source_url,
            confidence=score,
            stale_disclaimer=_is_stale(chunk),
        )
        for score, chunk in top3
        if chunk.source_url  # omit fabricated / empty URLs per CLAUDE.md
    ]

    needs_clarification = confidence < _CLARIFICATION_THRESHOLD

    # Evidentiary gate: don't let a single lucky/keyword-stuffed chunk pass
    # the clarification threshold on its own. Require corroboration from at
    # least _MIN_SUPPORTING_CHUNKS chunks that individually clear
    # _MIN_SUPPORTING_CHUNK_SCORE before confidence can suppress clarification.
    supporting_chunks = sum(
        1 for score, _ in scored if score > _MIN_SUPPORTING_CHUNK_SCORE
    )
    if not needs_clarification and supporting_chunks < _MIN_SUPPORTING_CHUNKS:
        needs_clarification = True

    log.info(
        "analyst_done",
        confidence=confidence,
        needs_clarification=needs_clarification,
        supporting_chunks=supporting_chunks,
        citations=len(citations),
    )
    return {
        "citations": citations,
        "confidence_score": confidence,
        "needs_clarification": needs_clarification,
    }
