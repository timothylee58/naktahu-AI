"""analyst_node — score citations, set confidence, flag clarification."""
from __future__ import annotations

import re
from datetime import date

import structlog
import weave

from app.agents.personal_data import detect_personal_data_agency
from app.core.prometheus_metrics import retrieval_score
from app.models.state import AgentState, Citation
from app.services.vector_store import ChunkResult

log = structlog.get_logger(__name__)

_GOV_DOMAIN_RE = re.compile(
    r"https?://(?:[\w\-]+\.)*(?:gov\.my|edu\.my|org\.my)(?:/|$)",
    re.IGNORECASE,
)

_CLARIFICATION_THRESHOLD = 0.6
# Domain-aware staleness windows. Kept in sync with the temporal_accuracy eval
# metric (scripts/evals/temporal_scorer.py) so runtime flagging and the deploy
# gate agree: policy domains that change often get a tighter window. Using
# effective_date semantics, a flat short window (e.g. 90d) would over-flag a
# rule that only just took effect, so windows are months/a year, not days.
_STRICT_DOMAINS = frozenset({"tax", "epf", "immigration"})
_STRICT_STALE_DAYS = 180
_DEFAULT_STALE_DAYS = 365
# Recency penalty applied to a stale chunk's relevance/authority score. Enough
# to let a fresher chunk outrank a stale one on the same topic (prefer-newest)
# and to pull confidence down when the only supporting evidence is stale,
# without hard-blocking (the synthesiser hedge does the user-facing work).
_STALE_PENALTY = 0.15
_MIN_SUPPORTING_CHUNK_SCORE = 0.3
_MIN_SUPPORTING_CHUNKS = 2


def _staleness_ref(chunk: ChunkResult) -> str | None:
    """The date used to judge staleness.

    Prefers ``effective_date`` (when the rule/figure actually takes effect —
    the meaningful signal). Falls back to ``source_date`` only for chunks
    explicitly marked ``expiry_aware``.
    """
    if chunk.effective_date:
        return chunk.effective_date
    if chunk.expiry_aware and chunk.source_date:
        return chunk.source_date
    return None


def _days_since_effective(chunk: ChunkResult) -> int | None:
    """Whole days since the chunk's effective/source date, or None if unknown
    or not yet in effect (future/today dates are never stale)."""
    ref = _staleness_ref(chunk)
    if not ref:
        return None
    try:
        ref_dt = date.fromisoformat(ref)
    except ValueError:
        return None
    days = (date.today() - ref_dt).days
    return days if days > 0 else None


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _is_pending(chunk: ChunkResult) -> bool:
    """Announced but not yet in force: effective_date is after today.

    Such a chunk is not evidence for today's rule — it describes the NEXT
    rule. Without this check, prefer-newest ranked it first and the answer
    stated a future rule as the current one.
    """
    start = _parse_date(chunk.effective_date)
    return start is not None and start > date.today()


def _is_expired(chunk: ChunkResult) -> bool:
    """The rule's validity window has closed (effective_until before today)."""
    end = _parse_date(chunk.effective_until)
    return end is not None and end < date.today()


_MAX_PENDING_CHANGES = 3
# When there is no rule in force at all and the answer is built from announced
# changes alone (e.g. "what did Budget 2027 announce for EPF?" asked before any
# of it takes effect), those chunks ARE the evidence, so allow more of them.
_MAX_PENDING_ANNOUNCED_ONLY = 5


def _pending_change(chunk: ChunkResult) -> dict:
    return {
        "chunk_id": chunk.id,
        "source_title": chunk.source_title,
        "ministry": chunk.ministry,
        "source_url": chunk.source_url,
        "effective_date": chunk.effective_date,
        "announced_date": chunk.announced_date,
        "content": chunk.content,
    }


def _build_citation(chunk: ChunkResult, score: float, domain: str | None, *, pending: bool = False) -> Citation:
    citation = Citation(
        title=chunk.source_title,
        ministry=chunk.ministry,
        url=chunk.source_url,
        confidence=score,
        # A rule that has not started cannot be stale.
        stale_disclaimer=False if pending else _is_stale(chunk, domain),
        # Same value the staleness verdict is computed from, so the date a
        # user sees and the "may be outdated" flag can never disagree. None
        # when the chunk has no date — the UI renders nothing rather than
        # inventing one.
        effective_date=_staleness_ref(chunk),
        retrieved_at=chunk.retrieved_at,
    )
    if pending:
        # Lets the UI say "takes effect {date}" instead of "in effect from".
        citation["not_yet_effective"] = True
    return citation


def _stale_threshold(domain: str | None) -> int:
    return _STRICT_STALE_DAYS if domain in _STRICT_DOMAINS else _DEFAULT_STALE_DAYS


def _is_stale(chunk: ChunkResult, domain: str | None = None) -> bool:
    days = _days_since_effective(chunk)
    return days is not None and days > _stale_threshold(domain)


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
    """Sortable recency key; missing dates sort oldest (empty string).

    Uses effective_date first (falls back to source_date) so prefer-newest
    ranks by when the rule takes effect, not when the doc was scraped.
    """
    return chunk.effective_date or chunk.source_date or ""


def _relevance_signal(chunk: ChunkResult, query: str) -> float:
    """Relevance in [0, 1]: the stronger of lexical keyword overlap and the
    retriever's semantic similarity.

    Keyword overlap alone under-scores cross-lingual and paraphrased matches:
    an English query against a Bahasa Malaysia chunk shares almost no tokens, so
    a semantically perfect chunk the retriever ranked highly (high cosine
    similarity) would score ~0 on overlap and get clarified away. Folding in
    ``chunk.similarity`` (the hybrid_search combined cosine+BM25 score) fixes
    that. ``max()`` — rather than a blend — keeps the change monotonic: every
    chunk scores at least as high as lexical overlap alone, so anything that
    answers today keeps answering; only semantic-only matches are lifted.
    """
    query_tokens = set(re.findall(r"\w+", query.lower()))
    content_tokens = set(re.findall(r"\w+", chunk.content.lower()))
    overlap = 0.0
    if query_tokens:
        overlap = len(query_tokens & content_tokens) / len(query_tokens)
    similarity = min(max(chunk.similarity, 0.0), 1.0)
    return min(max(overlap, similarity), 1.0)


def _score_chunk(chunk: ChunkResult, query: str) -> float:
    score = 0.0

    # URL is a real Malaysian government / education domain (+0.3)
    if chunk.source_url and _GOV_DOMAIN_RE.match(chunk.source_url):
        score += 0.3

    # Non-empty source title (+0.2)
    if chunk.source_title and chunk.source_title.strip():
        score += 0.2

    # Relevance — lexical overlap OR semantic similarity, whichever is stronger
    # (+0.5 max).
    score += _relevance_signal(chunk, query) * 0.5

    return round(min(score, 1.0), 4)


@weave.op()
async def analyst_node(state: AgentState) -> dict:
    """Score retrieved chunks, select top 3 citations, compute confidence.

    Before scoring, two freshness checks run (faithfulness/relevance can't see
    either):
      1. Superseded chunks (``superseded_by`` set) are hard-rejected — dropped
         from the retrieved set entirely so they can never be scored, cited, or
         seen by the synthesiser.
      2. Chunks whose ``effective_date`` passed more than the domain staleness
         window ago are recorded in ``stale_warnings`` and down-weighted, and the
         answer is flagged so the synthesiser date-stamps and hedges it.
    Validity windows (migration 052) are applied between the two: chunks whose
    ``effective_until`` has passed are dropped, and chunks whose
    ``effective_date`` is still in the future are returned as
    ``pending_changes`` rather than scored as today's rule.
    """
    query = state.get("query", "")
    domain = state.get("domain")
    retrieved: list[ChunkResult] = state.get("retrieved_chunks", [])
    agency_contact = detect_personal_data_agency(query, domain)

    # 1. Hard-reject superseded chunks (never cite a chunk a newer one replaces).
    #    Build a new list rather than mutating the input while iterating.
    live = [c for c in retrieved if c.superseded_by is None]
    superseded_count = len(retrieved) - len(live)
    if superseded_count:
        log.info("analyst_dropped_superseded", count=superseded_count)

    # 1b. Validity window. Expired rules (effective_until passed) are dropped
    #     like superseded ones. Pending rules (effective_date in the future)
    #     are not evidence for today's answer: they are set aside as
    #     pending_changes so the synthesiser states the current rule AND the
    #     announced change, instead of presenting the future rule as current.
    expired = [c for c in live if _is_expired(c)]
    chunks = [c for c in live if not _is_expired(c) and not _is_pending(c)]
    # Most relevant announced change first (then soonest to take effect), so the
    # few that fit in the answer's context are the ones the question is about,
    # not merely the earliest-dated.
    pending_scored = sorted(
        ((_score_chunk(c, query), c) for c in live if _is_pending(c) and not _is_expired(c)),
        key=lambda t: (-t[0], t[1].effective_date or ""),
    )
    pending = [c for _, c in pending_scored]
    announced_only = not chunks and bool(pending)
    cap = _MAX_PENDING_ANNOUNCED_ONLY if announced_only else _MAX_PENDING_CHANGES
    pending_changes = [_pending_change(c) for c in pending[:cap]]
    if expired or pending:
        log.info("analyst_validity_window", expired=len(expired), pending=len(pending), announced_only=announced_only)

    # 2. Record effective-date staleness for the surviving chunks.
    stale_warnings: list[dict] = []
    for chunk in chunks:
        if not _is_stale(chunk, domain):
            continue
        days_old = _days_since_effective(chunk)
        stale_warnings.append({
            "chunk_id": chunk.id,
            "source_title": chunk.source_title,
            "effective_date": _staleness_ref(chunk),
            "days_since_effective": days_old,
        })

    if not chunks and not pending:
        # Either nothing was retrieved, or everything retrieved was superseded.
        log.warning("analyst_no_usable_chunks", superseded_count=superseded_count)
        retrieval_score.observe(0.0)
        return {
            "retrieved_chunks": chunks,
            "citations": [],
            "confidence_score": 0.0,
            "needs_clarification": True,
            # All-superseded/expired is itself a staleness signal worth surfacing.
            "stale_warning": superseded_count > 0 or bool(expired),
            "answer_as_of": None,
            "stale_warnings": stale_warnings,
            "pending_changes": pending_changes,
            "agency_contact": agency_contact,
        }

    # (adjusted_score, recency_key, chunk). Recency-penalise stale chunks and
    # break score ties toward the most recent source (prefer-newest), so when
    # both last year's and this year's figure are in the corpus, the newer one
    # drives the answer.
    # With nothing in force, the announced changes are the evidence (see
    # announced_only above); they are never stale, so no recency penalty applies.
    evidence = pending if announced_only else chunks
    scored: list[tuple[float, str, ChunkResult]] = [
        (_adjusted_score(_score_chunk(chunk, query), _is_stale(chunk, domain)), _recency_key(chunk), chunk)
        for chunk in evidence
    ]
    scored.sort(key=lambda t: (t[0], t[1]), reverse=True)

    top3 = scored[:3]
    confidence = sum(s for s, _, _ in top3) / len(top3)
    retrieval_score.observe(confidence)

    citations: list[Citation] = [
        _build_citation(chunk, score, domain, pending=announced_only)
        for score, _, chunk in top3
        if chunk.source_url  # omit fabricated / empty URLs per CLAUDE.md
    ]
    if pending and not announced_only:
        # The answer will also mention the announced change, so cite it too —
        # keeping the 1-3 chip limit by giving up the weakest current citation.
        best_pending = pending[0]
        if best_pending.source_url and all(c["url"] != best_pending.source_url for c in citations):
            pending_citation = _build_citation(best_pending, pending_scored[0][0], domain, pending=True)
            citations = citations[:2] + [pending_citation]

    # Freshness verdict for the answer as a whole: after prefer-newest sorting,
    # the top-ranked chunk is the freshest sufficiently-relevant evidence. If it
    # is itself stale, the corpus has no current source for this query (e.g. the
    # new rule hasn't been ingested) — the synthesiser must date-stamp and hedge.
    top_chunk = top3[0][2]
    stale_warning = _is_stale(top_chunk, domain)
    answer_as_of = _staleness_ref(top_chunk) if stale_warning else None

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
        stale_warnings=len(stale_warnings),
        superseded_dropped=superseded_count,
        expired_dropped=len(expired),
        pending_changes=len(pending_changes),
        announced_only=announced_only,
        agency_contact=agency_contact["agency"] if agency_contact else None,
    )
    return {
        # Persist the superseded-pruned set so the synthesiser never builds
        # context from a chunk a newer one replaces.
        "retrieved_chunks": chunks,
        "citations": citations,
        "confidence_score": confidence,
        "needs_clarification": needs_clarification,
        "stale_warning": stale_warning,
        "answer_as_of": answer_as_of,
        "stale_warnings": stale_warnings,
        "pending_changes": pending_changes,
        "agency_contact": agency_contact,
    }
