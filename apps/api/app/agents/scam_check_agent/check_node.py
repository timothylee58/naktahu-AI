"""Deterministic URL/domain verification against official_gov_domains
(migration 046) — no LLM involved in this node at all.

This is the safety-critical node. A verdict of "verified_official" or
"impersonation_risk" must come from an exact or near-match against the
curated reference table, never from model judgment — the LLM in
synthesiser_node only explains a verdict this node already reached, the
same "deterministic-first, LLM-explains-second" split
welfare_eligibility_agent's match_node uses for scheme matching. A domain
NOT in official_gov_domains is reported as "unverified" (we don't know),
never as "safe" or "unofficial" — the reference list is necessarily
incomplete, and treating absence-from-list as evidence of fraud (or of
legitimacy) would be a worse failure than an honest "can't verify this".
"""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlsplit

import structlog

from app.agents.scam_check_agent.state import ExtractedDomainCheck, ScamCheckState, Verdict

log = structlog.get_logger(__name__)

# Matches bare domains too (no scheme), since scam SMS rarely include
# "https://" — e.g. "hasil-refund.gov.my.claim-now.cc/verify".
_URL_RE = re.compile(
    r"(?:https?://)?(?:www\.)?"
    r"([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+)"
    r"(?:/[^\s]*)?",
    re.IGNORECASE,
)

# Deterministic, given-not-invented red flags for the LLM to explain —
# covers the actual scam-copy vocabulary seen in real LHDN/JPJ/EPF
# impersonation SMS (urgency, threat of penalty, request for payment/OTP).
_RED_FLAG_PATTERNS: dict[str, re.Pattern[str]] = {
    "urgency_language": re.compile(r"\b(urgent|segera|immediately|serta.?merta|final notice|notis akhir)\b", re.IGNORECASE),
    "penalty_threat": re.compile(r"\b(denda|penalty|suspended|digantung|blacklist|disenaraihitam|account.{0,10}locked|akaun.{0,10}dikunci)\b", re.IGNORECASE),
    "requests_payment_or_otp": re.compile(r"\b(otp|one.?time.?password|bank.{0,10}details|no\.?\s*akaun|card number|nombor kad|klik.{0,10}link|click.{0,10}link)\b", re.IGNORECASE),
    "refund_claim": re.compile(r"\b(refund|bayaran balik|tuntutan|claim.{0,10}now|tuntut.{0,10}sekarang)\b", re.IGNORECASE),
}


def _normalise_domain(raw: str) -> str:
    return raw.strip().lower().removeprefix("www.")


def _extract_urls(text: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for m in _URL_RE.finditer(text):
        domain = _normalise_domain(m.group(1))
        # Require at least one dot and a plausible TLD-length tail to avoid
        # matching ordinary sentence fragments ("e.g." etc.) as domains.
        if "." not in domain or len(domain.rsplit(".", 1)[-1]) < 2:
            continue
        if domain not in seen:
            seen.add(domain)
            out.append(domain)
    return out


def _levenshtein(a: str, b: str) -> int:
    """Small pure-Python edit distance — no new dependency for this one
    lookup. Reference table is ~15 rows; this runs at most a few dozen
    times per request, not a hot path."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        curr = [i] + [0] * len(b)
        for j, cb in enumerate(b, start=1):
            cost = 0 if ca == cb else 1
            curr[j] = min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost)
        prev = curr
    return prev[-1]


def _hostname_from_url(url: str) -> str:
    """urlsplit needs a scheme to parse netloc correctly — _extract_urls
    already stripped scheme/www, so re-add one just for parsing."""
    parsed = urlsplit(url if "://" in url else f"//{url}")
    return _normalise_domain(parsed.hostname or url)


def _check_domain(domain: str, official_domains: list[dict[str, Any]]) -> ExtractedDomainCheck:
    for row in official_domains:
        if domain == row["domain"]:
            return {
                "url": domain,
                "domain": domain,
                "verdict": "verified_official",
                "matched_institution": row["institution_name"],
                "matched_domain": row["domain"],
            }

    # Typosquat / impersonation check: close edit-distance to a real
    # official domain, or the real domain's core label present with a
    # wrong TLD (e.g. "hasil.gov.my.claim-now.cc" or "hasil-gov.my").
    for row in official_domains:
        official = row["domain"]
        label = official.split(".")[0]  # e.g. "hasil" from "hasil.gov.my"
        if len(label) >= 3 and label in domain and domain != official:
            return {
                "url": domain,
                "domain": domain,
                "verdict": "impersonation_risk",
                "matched_institution": row["institution_name"],
                "matched_domain": official,
            }
        if _levenshtein(domain, official) <= 2 and domain != official:
            return {
                "url": domain,
                "domain": domain,
                "verdict": "impersonation_risk",
                "matched_institution": row["institution_name"],
                "matched_domain": official,
            }

    return {"url": domain, "domain": domain, "verdict": "unverified", "matched_institution": None, "matched_domain": None}


def _scan_red_flags(text: str) -> list[str]:
    return [name for name, pattern in _RED_FLAG_PATTERNS.items() if pattern.search(text)]


_VERDICT_SEVERITY: dict[Verdict, int] = {
    "impersonation_risk": 3,
    "unverified": 2,
    "verified_official": 1,
    "no_url_found": 0,
}


async def check_node(state: ScamCheckState, supabase: Any) -> dict[str, Any]:
    text = state.get("input_text", "") or ""
    urls = _extract_urls(text)
    red_flags = _scan_red_flags(text)

    if not urls:
        return {
            "checks": [],
            "overall_verdict": "no_url_found",
            "text_red_flags": red_flags,
        }

    official_domains: list[dict[str, Any]] = []
    if supabase:
        try:
            res = (
                supabase.table("official_gov_domains")
                .select("institution_name,domain")
                .execute()
            )
            official_domains = res.data or []
        except Exception as exc:
            log.warning("official_gov_domains_fetch_failed", error=str(exc))

    checks = [_check_domain(_hostname_from_url(url), official_domains) for url in urls]
    overall = max((c["verdict"] for c in checks), key=lambda v: _VERDICT_SEVERITY[v]) if checks else "no_url_found"

    return {"checks": checks, "overall_verdict": overall, "text_red_flags": red_flags}
