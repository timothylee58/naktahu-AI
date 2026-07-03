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
# Recency penalty applied to a stale chunk's relevance/authority score. Enough
# to let a fresher chunk outrank a stale one on the same topic (prefer-newest)
# and to pull confidence down when the only supporting evidence is stale,
# without hard-blocking (the synthesiser hedge does the user-facing work).
_STALE_PENALTY = 0.15
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


def _adjusted_score(base: float, stale: bool) -> float:
    """Relevance/authority score with a recency penalty for stale evidence.

    Relevance/faithfulness says nothing about whether a chunk is still current,
    so a stale chunk is down-weighted here. This is the piece that makes a
    stale-but-faithful chunk *observable* to the confidence/citation layer
    instead of scoring identically to a fresh one.
    """
    if stale:
        return round(max(base - _STALE_PENALTY, 0.0), 4)
    return base


def _recency_key(chunk: ChunkResult) -> str:
    """Sortable recency key; missing dates sort oldest (empty string)."""
    return chunk.source_date or ""


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
            "stale_warning": False,
            "answer_as_of": None,
        }

    # (adjusted_score, recency_key, chunk). Recency-penalise stale chunks and
    # break score ties toward the most recent source (prefer-newest), so when
    # both last year's and this year's figure are in the corpus, the newer one
    # drives the answer.
    scored: list[tuple[float, str, ChunkResult]] = [
        (_adjusted_score(_score_chunk(chunk, query), _is_stale(chunk)), _recency_key(chunk), chunk)
        for chunk in chunks
    ]
    scored.sort(key=lambda t: (t[0], t[1]), reverse=True)

    top3 = scored[:3]
    confidence = sum(s for s, _, _ in top3) / len(top3)

    citations: list[Citation] = [
        Citation(
            title=chunk.source_title,
            ministry=chunk.ministry,
            url=chunk.source_url,
            confidence=score,
            stale_disclaimer=_is_stale(chunk),
        )
        for score, _, chunk in top3
        if chunk.source_url  # omit fabricated / empty URLs per CLAUDE.md
    ]

    # Freshness verdict for the answer as a whole: after prefer-newest sorting,
    # the top-ranked chunk is the freshest sufficiently-relevant evidence. If it
    # is itself stale, the corpus has no current source for this query (e.g. the
    # new rule hasn't been ingested) — the synthesiser must date-stamp and hedge.
    top_chunk = top3[0][2]
    stale_warning = _is_stale(top_chunk)
    answer_as_of = top_chunk.source_date if stale_warning else None

    needs_clarification = confidence < _CLARIFICATION_THRESHOLD

    # Evidentiary gate: don't let a single lucky/keyword-stuffed chunk pass
    # the clarification threshold on its own. Require corroboration from at
    # least _MIN_SUPPORTING_CHUNKS chunks that individually clear
    # _MIN_SUPPORTING_CHUNK_SCORE before confidence can suppress clarification.
    supporting_chunks = sum(
        1 for score, _, _ in scored if score > _MIN_SUPPORTING_CHUNK_SCORE
    )
    if not needs_clarification and supporting_chunks < _MIN_SUPPORTING_CHUNKS:
        needs_clarification = True

    log.info(
        "analyst_done",
        confidence=confidence,
        needs_clarification=needs_clarification,
        supporting_chunks=supporting_chunks,
        citations=len(citations),
        stale_warning=stale_warning,
        answer_as_of=answer_as_of,
    )
    return {
        "citations": citations,
        "confidence_score": confidence,
        "needs_clarification": needs_clarification,
        "stale_warning": stale_warning,
        "answer_as_of": answer_as_of,
    }
