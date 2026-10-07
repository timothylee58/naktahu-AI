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

# Whitespace-delimited tokens containing a dot — deliberately loose. The
# *real* parsing (including correctly resolving userinfo like
# "hasil.gov.my@evil.com" to host "evil.com", which a hand-rolled domain
# regex gets wrong — see _hostname_from_url) is delegated entirely to
# urlsplit, not done here. This just finds candidate tokens worth parsing.
_TOKEN_RE = re.compile(r"\S+\.\S+")

_TLD_RE = re.compile(r"^[a-z]{2,}$", re.IGNORECASE)

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


def _hostname_from_url(token: str) -> str | None:
    """Resolve the token's real, browser-would-connect-to host — the only
    correct source of truth for this is urlsplit's `.hostname`, which
    (per RFC 3986) parses `user:pass@host` netloc syntax and returns just
    `host`. A hand-rolled domain-charset regex applied directly to the raw
    token gets this wrong: for "https://hasil.gov.my@evil.com/verify" it
    would greedily capture "hasil.gov.my" (stopping at '@') and report
    that as the domain, when the browser actually connects to "evil.com" —
    inverting the safety check entirely (a bait host wrapped in a real
    institution's name as fake "credentials" reads as verified_official).
    Confirmed bug from an automated review of this file's first version;
    fixed by handing the *whole* token to urlsplit instead of pre-parsing
    it with a regex.

    `urlsplit` needs a scheme to parse netloc correctly; token has none
    reliably (scam SMS rarely include "https://"), so one is added only
    for parsing.
    """
    candidate = token if "://" in token else f"//{token}"
    parsed = urlsplit(candidate)
    hostname = parsed.hostname
    if not hostname:
        return None
    return _normalise_domain(hostname)


def _extract_urls(text: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for m in _TOKEN_RE.finditer(text):
        hostname = _hostname_from_url(m.group(0))
        if not hostname or "." not in hostname:
            continue
        # Require a plausible alphabetic TLD to avoid matching ordinary
        # sentence fragments ("e.g.", "no.5") as domains.
        if not _TLD_RE.match(hostname.rsplit(".", 1)[-1]):
            continue
        if hostname not in seen:
            seen.add(hostname)
            out.append(hostname)
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


def _is_official_or_subdomain(domain: str, official: str) -> bool:
    """A real subdomain of an official domain (mytax.hasil.gov.my,
    i-akaun.kwsp.gov.my) is legitimately part of that institution's own
    namespace — must be verified_official, never flagged. Confirmed bug
    fix: the first version's substring check ("hasil" in domain) flagged
    exactly these as impersonation_risk."""
    return domain == official or domain.endswith("." + official)


def _looks_like_impersonation(domain: str, official: str) -> bool:
    """Two narrow, deliberately conservative impersonation signals —
    replacing the first version's `official_label in domain` substring
    check, which also matched real government subdomains (bug above) AND
    unrelated hosts sharing a short label by coincidence (confirmed: "pos"
    — the label for pos.com.my — is a substring of "compose.com"; "imi" —
    imi.gov.my — is a substring of dozens of unrelated words). Both
    signals below require a component/prefix boundary, not a bare
    substring:

    1. `official` appears as a leading, dot-bounded prefix of a LONGER
       domain (the classic "hasil.gov.my.claim-now.cc" bait — official
       domain first, so a skimming reader sees the real name, then more
       attacker-controlled labels after it). Exact-domain and real
       subdomains are already handled by _is_official_or_subdomain above
       and never reach this check.
    2. The official domain's first label (e.g. "hasil") appears as an
       EXACT dot/hyphen-delimited component of `domain`, not merely a
       substring — "compose.com" splits to {"compose", "com"}, so "pos"
       (a substring of "compose", not a component) no longer matches;
       "hasil-refund.gov.my.claim-now.cc" splits to a set containing
       "hasil" exactly, so it still matches. Gated to labels of at least
       4 characters — official labels shorter than that (imi, pos, rmp,
       bnm, jpn, ssm, moh — half the seed list) are deliberately EXCLUDED
       from this embedding check, since a 3-character exact-component
       match is still too likely to hit an unrelated real word by chance.
       Those institutions are still covered by the exact/subdomain and
       Levenshtein checks on the full domain string, just not this
       "embedded as a prefix label" pattern specifically — an intentional
       under-detection tradeoff, not an oversight.
    """
    if domain != official and domain.startswith(official + "."):
        return True
    label = official.split(".")[0]
    if len(label) >= 4:
        components = set(re.split(r"[.-]", domain))
        if label in components:
            return True
    return False


def _check_domain(domain: str, official_domains: list[dict[str, Any]]) -> ExtractedDomainCheck:
    for row in official_domains:
        if _is_official_or_subdomain(domain, row["domain"]):
            return {
                "url": domain,
                "domain": domain,
                "verdict": "verified_official",
                "matched_institution": row["institution_name"],
                "matched_domain": row["domain"],
            }

    for row in official_domains:
        official = row["domain"]
        if _looks_like_impersonation(domain, official):
            return {
                "url": domain,
                "domain": domain,
                "verdict": "impersonation_risk",
                "matched_institution": row["institution_name"],
                "matched_domain": official,
            }
        # Typo distance, guarded by a length gate so two short-but-unrelated
        # domains can't coincidentally land within edit-distance 2 of each
        # other (e.g. "pos.com.my" vs some unrelated 9-char domain).
        if (
            domain != official
            and abs(len(domain) - len(official)) <= 2
            and _levenshtein(domain, official) <= 2
        ):
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

    checks = [_check_domain(url, official_domains) for url in urls]
    overall = max((c["verdict"] for c in checks), key=lambda v: _VERDICT_SEVERITY[v]) if checks else "no_url_found"

    return {"checks": checks, "overall_verdict": overall, "text_red_flags": red_flags}
