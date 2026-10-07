"""Shared freshness rules for retrieved chunks.

One definition of "current", "announced but not in force", "expired",
"superseded" and "stale", used by every consumer of ``ChunkResult`` rows so the
answer pipeline (``analyst_node``) and the report builders (Compliance Drafter)
can never disagree about what is in force today.

Everything here is pure: it reads the freshness fields of a ``ChunkResult``
(``effective_date``, ``effective_until``, ``announced_date``, ``superseded_by``,
``expiry_aware``, ``source_date``) and ``date.today()``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from app.services.vector_store import ChunkResult

# Domain-aware staleness windows. Kept in sync with the temporal_accuracy eval
# metric (scripts/evals/temporal_scorer.py) so runtime flagging and the deploy
# gate agree: policy domains that change often get a tighter window. Using
# effective_date semantics, a flat short window (e.g. 90d) would over-flag a
# rule that only just took effect, so windows are months/a year, not days.
STRICT_DOMAINS = frozenset({"tax", "epf", "immigration"})
STRICT_STALE_DAYS = 180
DEFAULT_STALE_DAYS = 365


def staleness_ref(chunk: ChunkResult) -> str | None:
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


def days_since_effective(chunk: ChunkResult) -> int | None:
    """Whole days since the chunk's effective/source date, or None if unknown
    or not yet in effect (future/today dates are never stale)."""
    ref = staleness_ref(chunk)
    if not ref:
        return None
    try:
        ref_dt = date.fromisoformat(ref)
    except ValueError:
        return None
    days = (date.today() - ref_dt).days
    return days if days > 0 else None


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def is_pending(chunk: ChunkResult) -> bool:
    """Announced but not yet in force: effective_date is after today.

    Such a chunk is not evidence for today's rule — it describes the NEXT
    rule. Without this check, prefer-newest ranked it first and the answer
    stated a future rule as the current one.
    """
    start = parse_date(chunk.effective_date)
    return start is not None and start > date.today()


def is_expired(chunk: ChunkResult) -> bool:
    """The rule's validity window has closed (effective_until before today)."""
    end = parse_date(chunk.effective_until)
    return end is not None and end < date.today()


def is_superseded(chunk: ChunkResult) -> bool:
    """A newer chunk replaces this one; it must never be cited or listed."""
    return chunk.superseded_by is not None


def stale_threshold(domain: str | None) -> int:
    return STRICT_STALE_DAYS if domain in STRICT_DOMAINS else DEFAULT_STALE_DAYS


def is_stale(chunk: ChunkResult, domain: str | None = None) -> bool:
    days = days_since_effective(chunk)
    return days is not None and days > stale_threshold(domain)


def pending_change(chunk: ChunkResult) -> dict:
    return {
        "chunk_id": chunk.id,
        "source_title": chunk.source_title,
        "ministry": chunk.ministry,
        "source_url": chunk.source_url,
        "effective_date": chunk.effective_date,
        "announced_date": chunk.announced_date,
        "content": chunk.content,
    }


@dataclass
class FreshnessPartition:
    """Chunks split by validity, each list keeping the input order.

    ``current``    in force today (not superseded, not expired, not future-dated)
    ``announced``  effective_date in the future, not expired, not superseded
    ``superseded`` / ``expired``  dropped; kept only so callers can count them
    """

    current: list[ChunkResult] = field(default_factory=list)
    announced: list[ChunkResult] = field(default_factory=list)
    superseded: list[ChunkResult] = field(default_factory=list)
    expired: list[ChunkResult] = field(default_factory=list)


def partition_by_freshness(chunks: list[ChunkResult]) -> FreshnessPartition:
    """Split chunks into current / announced / superseded / expired.

    Precedence matches the answer pipeline: superseded wins over everything,
    then expired (a closed window beats a future start date), then pending.
    """
    out = FreshnessPartition()
    for chunk in chunks:
        if is_superseded(chunk):
            out.superseded.append(chunk)
        elif is_expired(chunk):
            out.expired.append(chunk)
        elif is_pending(chunk):
            out.announced.append(chunk)
        else:
            out.current.append(chunk)
    return out
