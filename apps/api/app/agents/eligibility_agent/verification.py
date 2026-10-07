"""Live verification of matched grants' deadlines against the agency's own site.

`grant_database.application_deadline` goes stale: intake windows open, close and
move. After the analyst has matched grants, this module re-checks each one
against the agency's published page (via Tavily) and attaches a `verification`
record to the grant:

    confirmed    the page states the same deadline we hold
    changed      the page states a different deadline (we do NOT overwrite the
                 database — both dates are returned for a human to review)
    closed       the page says applications are closed
    no_signal    the page was reached but states no deadline or closure
    unavailable  not checked (no API key, no agency URL, timeout or error)

Design rules, all deliberate:
  * Search is restricted to the hostname of the grant's own `application_url` /
    `source_url`. We never search the open web and never cite a URL that did not
    come back from that domain, so a verification stamp cannot carry a
    fabricated or third-party source.
  * Extraction is deterministic (dates near deadline keywords, closure phrases).
    No LLM reads web text here, so there is no new prompt-injection surface; the
    short evidence excerpt is also run through the shared injection scan before
    it is returned.
  * `unavailable` is never reported as a pass. An unverified grant is shown as
    unverified, with the date we last verified it ourselves.
  * Never raises: any failure degrades to `unavailable` (Trap #4 spirit).
"""
from __future__ import annotations

import asyncio
import hashlib
import re
import unicodedata
from datetime import date, datetime, timezone
from typing import Any, Optional
from urllib.parse import urlparse

import structlog

from app.middleware.sanitise import INJECTION_PATTERNS, _fold_confusables
from app.services.cache import get_cached_result, set_cached_result
from core.config import settings

log = structlog.get_logger(__name__)

CONFIRMED = "confirmed"
CHANGED = "changed"
CLOSED = "closed"
NO_SIGNAL = "no_signal"
UNAVAILABLE = "unavailable"

MAX_GRANTS_VERIFIED = 5
_CONCURRENCY = 3
_CALL_TIMEOUT_S = 10.0
_CACHE_TTL_S = 6 * 3600
_EVIDENCE_MAX_CHARS = 200

_MONTHS = {
    "jan": 1, "januari": 1, "january": 1,
    "feb": 2, "februari": 2, "february": 2,
    "mar": 3, "mac": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5, "mei": 5,
    "jun": 6, "june": 6,
    "jul": 7, "julai": 7, "july": 7,
    "aug": 8, "ogos": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "okt": 10, "october": 10, "oktober": 10,
    "nov": 11, "november": 11,
    "dec": 12, "dis": 12, "december": 12, "disember": 12,
}

_ISO_DATE = re.compile(r"\b(20\d{2})-(\d{2})-(\d{2})\b")
_TEXT_DATE = re.compile(r"\b(\d{1,2})\s+([A-Za-z]{3,9})\.?,?\s+(20\d{2})\b")
_DEADLINE_WORDS = re.compile(
    r"deadline|closing\s+date|closes?\b|apply\s+by|applications?\s+(?:close|due)|"
    r"tarikh\s+(?:tutup|akhir)|tarikh\s+luput|ditutup\s+pada|tutup\s+pada",
    re.IGNORECASE,
)
_CLOSED_PHRASES = re.compile(
    r"applications?\s+(?:are\s+|is\s+)?(?:now\s+)?closed|intake\s+(?:is\s+)?closed|"
    r"no\s+longer\s+accepting|telah\s+ditutup|permohonan\s+(?:telah\s+)?ditutup",
    re.IGNORECASE,
)


def _hostname(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    host = (urlparse(url).hostname or "").lower()
    host = host[4:] if host.startswith("www.") else host
    return host or None


def _same_site(url: str, host: str) -> bool:
    candidate = _hostname(url)
    return bool(candidate) and (candidate == host or candidate.endswith("." + host))


def _dates_with_context(text: str) -> list[tuple[date, str]]:
    """Every parseable date that sits within 80 chars after a deadline keyword."""
    found: list[tuple[date, str]] = []
    matches: list[tuple[int, date]] = []
    for m in _ISO_DATE.finditer(text):
        try:
            matches.append((m.start(), date(int(m[1]), int(m[2]), int(m[3]))))
        except ValueError:
            continue
    for m in _TEXT_DATE.finditer(text):
        month = _MONTHS.get(m[2].lower())
        if not month:
            continue
        try:
            matches.append((m.start(), date(int(m[3]), month, int(m[1]))))
        except ValueError:
            continue
    for pos, d in matches:
        window = text[max(0, pos - 80):pos]
        if _DEADLINE_WORDS.search(window):
            found.append((d, text[max(0, pos - 80):pos + 40]))
    return found


def _safe_excerpt(text: str) -> Optional[str]:
    cleaned = " ".join(text.split())[:_EVIDENCE_MAX_CHARS]
    folded = _fold_confusables(unicodedata.normalize("NFKC", cleaned))
    if any(p.search(folded) for p in INJECTION_PATTERNS):
        return None
    return cleaned or None


def _parse_db_deadline(value: Any) -> Optional[date]:
    try:
        return date.fromisoformat(str(value)[:10]) if value else None
    except ValueError:
        return None


def assess_results(
    results: list[dict[str, Any]], host: str, db_deadline: Optional[date]
) -> dict[str, Any]:
    """Turn raw search results into a verification record (pure, no I/O)."""
    pages = [r for r in results if r.get("url") and _same_site(str(r["url"]), host)]
    if not pages:
        return {"status": UNAVAILABLE, "reason": "no_result_on_agency_site"}

    best = pages[0]
    text = " ".join(str(r.get("content") or "") for r in pages)
    closed = bool(_CLOSED_PHRASES.search(text))
    candidates = _dates_with_context(text)
    distinct = {d for d, _ in candidates}

    found: Optional[date] = None
    evidence: Optional[str] = None
    if len(distinct) == 1:
        found = next(iter(distinct))
        evidence = _safe_excerpt(candidates[0][1])

    if closed:
        status = CLOSED
    elif found is not None and db_deadline is not None:
        status = CONFIRMED if found == db_deadline else CHANGED
    elif found is not None:
        status = CHANGED
    else:
        status = NO_SIGNAL

    record: dict[str, Any] = {
        "status": status,
        "source_url": str(best["url"]),
        "source_domain": host,
        "db_deadline": db_deadline.isoformat() if db_deadline else None,
        "found_deadline": found.isoformat() if found else None,
        "ambiguous_dates": len(distinct) > 1,
    }
    if evidence:
        record["evidence"] = evidence
    return record


async def _search(client: Any, grant: dict[str, Any], host: str) -> list[dict[str, Any]]:
    year = datetime.now(timezone.utc).year
    query = f"{grant.get('programme_name', '')} application deadline intake {year}"
    resp = await asyncio.wait_for(
        client.search(query, search_depth="basic", max_results=3, include_domains=[host]),
        timeout=_CALL_TIMEOUT_S,
    )
    return list((resp or {}).get("results") or [])


def _cache_key(programme: str, host: str, today: date) -> str:
    raw = f"{programme.lower().strip()}|{host}|{today.isoformat()}"
    return "cache:grant_verify:" + hashlib.sha256(raw.encode()).hexdigest()


async def verify_grant(
    grant: dict[str, Any], client: Any, *, today: Optional[date] = None
) -> dict[str, Any]:
    """Verify one grant. Always returns a record carrying `checked_at`."""
    now = datetime.now(timezone.utc)
    today = today or now.date()
    stamp = {"checked_at": now.isoformat()}
    host = _hostname(grant.get("application_url") or grant.get("source_url"))
    programme = str(grant.get("programme_name") or "")
    if client is None:
        return {"status": UNAVAILABLE, "reason": "not_configured", **stamp}
    if not host or not programme:
        return {"status": UNAVAILABLE, "reason": "no_agency_url", **stamp}

    key = _cache_key(programme, host, today)
    cached = await get_cached_result(key)
    if isinstance(cached, dict) and cached.get("status"):
        return cached

    try:
        results = await _search(client, grant, host)
    except Exception as exc:  # network, quota, timeout: degrade, never raise
        log.warning("grant_verify_failed", programme=programme[:60], error=type(exc).__name__)
        return {"status": UNAVAILABLE, "reason": "search_failed", **stamp}

    record = {**assess_results(results, host, _parse_db_deadline(grant.get("application_deadline"))), **stamp}
    if record["status"] != UNAVAILABLE:
        await set_cached_result(key, record, ttl=_CACHE_TTL_S)
    return record


def _make_client() -> Any:
    """Tavily's official async client, or None when unconfigured/not installed."""
    if not settings.tavily_api_key:
        return None
    try:
        from tavily import AsyncTavilyClient  # type: ignore[import-not-found]
    except ImportError:
        log.warning("tavily_not_installed")
        return None
    return AsyncTavilyClient(api_key=settings.tavily_api_key)


async def verify_grants(
    grants: list[dict[str, Any]], *, client: Any = None, use_default_client: bool = True
) -> list[dict[str, Any]]:
    """Return copies of `grants` with a `verification` record on each.

    Only the first MAX_GRANTS_VERIFIED are checked (matched grants arrive ranked
    best-first); the rest are marked unavailable so the UI never implies they
    were checked. Input dicts are not mutated.
    """
    if client is None and use_default_client:
        client = _make_client()
    sem = asyncio.Semaphore(_CONCURRENCY)

    async def _one(index: int, grant: dict[str, Any]) -> dict[str, Any]:
        if index >= MAX_GRANTS_VERIFIED:
            record = {
                "status": UNAVAILABLE,
                "reason": "not_checked_limit",
                "checked_at": datetime.now(timezone.utc).isoformat(),
            }
        else:
            async with sem:
                record = await verify_grant(grant, client)
        return {**grant, "verification": record}

    return list(await asyncio.gather(*(_one(i, g) for i, g in enumerate(grants))))


async def verify_node(state: Any) -> dict[str, Any]:
    """LangGraph node: attach live verification to the analyst's matched grants."""
    matched = state.get("matched_grants") or []
    if not matched:
        return {}
    return {"matched_grants": await verify_grants(matched)}
