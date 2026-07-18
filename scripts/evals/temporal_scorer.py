"""Custom ``temporal_accuracy`` metric — chunk currency ("is this chunk current
as of today's date?"), the axis RAGAS faithfulness cannot measure.

RAGAS **faithfulness** scores *answer-to-chunk* consistency: a stale chunk
reproduced perfectly scores 1.0 faithful while being factually wrong (e.g. last
year's EPF withdrawal cap). ``temporal_accuracy`` scores each retrieved chunk's
*currency* from its metadata (``effective_date`` / ``superseded_by``), so an
eval gate can catch stale-but-faithful answers that faithfulness waves through.

Pure-Python and deterministic (no LLM call). Use it standalone via
``score_temporal_accuracy`` / ``aggregate_temporal_accuracy`` / the
``temporal_accuracy`` metric object, or plug it into RAGAS as a custom metric
(see ``scripts/evals/README.md``).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Iterable, Mapping, Optional, Union

# Policy domains whose rules change frequently → tighter recency requirement.
STRICT_DOMAINS = frozenset({"tax", "epf", "immigration"})
_STRICT_THRESHOLD_DAYS = 180
_DEFAULT_THRESHOLD_DAYS = 365

# Default pass bar for the eval gate. temporal_accuracy below this fails.
TEMPORAL_ACCURACY_GATE = 0.6

# Score returned when a chunk carries no date metadata — unknown currency,
# treated as moderately risky rather than trusted.
_UNKNOWN_SCORE = 0.5

DateLike = Union[date, str, None]


def _coerce_date(value: DateLike) -> Optional[date]:
    """Accept a ``date`` or ISO ``str`` (or None); return a ``date`` or None."""
    if value is None:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def _threshold_days(domain: str | None) -> int:
    return _STRICT_THRESHOLD_DAYS if domain in STRICT_DOMAINS else _DEFAULT_THRESHOLD_DAYS


def score_temporal_accuracy(
    chunk_effective_date: DateLike,
    chunk_superseded_by: str | None,
    domain: str | None = None,
    *,
    today: date | None = None,
) -> float:
    """Score 0.0–1.0 for a single chunk's currency.

    - superseded chunk (a newer version exists)  -> 0.0  (hard fail)
    - no ``effective_date`` metadata             -> 0.5  (unknown, risky)
    - not yet in effect / within domain window   -> 1.0
    - within 2x the domain window                -> 0.6
    - older                                       -> linear decay, floored at 0.1

    Strict domains (tax, epf, immigration) use a 180-day window; others 365.
    This catches what RAGAS faithfulness cannot: a factually-outdated but
    faithfully-reproduced chunk.
    """
    # Hard fail: chunk is explicitly superseded by a newer one.
    if chunk_superseded_by is not None:
        return 0.0

    effective = _coerce_date(chunk_effective_date)
    if effective is None:
        # No date metadata — treat as moderately risky.
        return _UNKNOWN_SCORE

    ref = today or date.today()
    days_old = (ref - effective).days
    if days_old < 0:
        # Rule takes effect in the future — treat as current.
        return 1.0

    threshold = _threshold_days(domain)
    if days_old <= threshold:
        return 1.0
    if days_old <= threshold * 2:
        return 0.6
    return max(0.1, 1.0 - (days_old / (threshold * 4)))


def _extract_chunk_meta(
    chunk: Any, default_domain: str | None
) -> tuple[DateLike, str | None, str | None]:
    """Pull (effective_date, superseded_by, domain) from a dict or object."""
    if isinstance(chunk, Mapping):
        eff = chunk.get("effective_date")
        sup = chunk.get("superseded_by")
        dom = chunk.get("domain", default_domain)
    else:
        eff = getattr(chunk, "effective_date", None)
        sup = getattr(chunk, "superseded_by", None)
        dom = getattr(chunk, "domain", None)
    return eff, sup, dom if dom is not None else default_domain


def aggregate_temporal_accuracy(
    chunks: Iterable[Any],
    domain: str | None = None,
    *,
    today: date | None = None,
) -> float:
    """Worst-case ``temporal_accuracy`` across the chunks used for an answer.

    Uses the **minimum** per-chunk score: an answer can be no more current than
    the least-current source it relies on, so one stale/superseded chunk taints
    the sample. Accepts ``ChunkResult``-like objects or dicts. Returns the
    unknown score (0.5) for an empty set.

    ``domain`` is the query/answer domain used to pick the recency window when a
    chunk does not carry its own ``domain``.
    """
    scores = [
        score_temporal_accuracy(*_extract_chunk_meta(chunk, domain), today=today)
        for chunk in chunks
    ]
    return min(scores) if scores else _UNKNOWN_SCORE


@dataclass
class TemporalAccuracy:
    """RAGAS-style custom metric object for chunk currency.

    Mirrors the RAGAS metric duck-type (``name`` + ``higher_is_better`` + a
    per-sample ``score``), so it can be used directly by our eval harness and is
    easy to register with RAGAS if that dependency is added. A "sample" is a
    mapping with ``retrieved_chunks`` (and optionally ``domain``), matching the
    contexts RAGAS already carries per row.
    """

    name: str = "temporal_accuracy"
    higher_is_better: bool = True
    gate: float = TEMPORAL_ACCURACY_GATE

    def score(self, sample: Mapping[str, Any], *, today: date | None = None) -> float:
        return aggregate_temporal_accuracy(
            sample.get("retrieved_chunks", []),
            domain=sample.get("domain"),
            today=today,
        )

    def passes(self, sample: Mapping[str, Any], *, today: date | None = None) -> bool:
        return self.score(sample, today=today) >= self.gate


# Ready-to-use singleton.
temporal_accuracy = TemporalAccuracy()
