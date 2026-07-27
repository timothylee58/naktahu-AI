"""Grant stacking compatibility checker.

Given a set of grant programmes a founder intends to apply for at the same
time, produce a three-state compatibility verdict for every unordered pair:

    stackable        can be claimed together with no restriction
    partial_overlap  both may be held, but NOT claimed against the same
                     project cost / expense line (`overlap_scope` says which)
    conflict         mutually exclusive — cannot hold both
    unknown          nobody has verified this pair

`unknown` is deliberate and load-bearing. Defaulting an unverified pair to
"stackable" is the dangerous failure mode: it tells a founder two grants
stack when no agency has said so. Absence of a rule is never evidence of
compatibility.

Sources, in priority order:
  1. `grant_compatibility_rules` (migration 021) — three-state, scoped,
     bilingually explained, sourced.
  2. `grant_database.stackable_with` / `.conflicts_with` text[] arrays
     (migration 020) — binary only, used as a fallback so the checker keeps
     working before 021 is pasted into the SQL editor (Trap #5).

No emoji or symbol mapping lives here — this module returns machine-readable
enum strings; presentation (✓ / ⚠ / ✗) belongs to the frontend and the
synthesiser.
"""
from __future__ import annotations

from itertools import combinations
from typing import Any, Optional

import structlog

log = structlog.get_logger(__name__)

STACKABLE = "stackable"
PARTIAL_OVERLAP = "partial_overlap"
CONFLICT = "conflict"
UNKNOWN = "unknown"

SOURCE_RULES_TABLE = "rules_table"
SOURCE_LEGACY_ARRAY = "legacy_array"
SOURCE_NONE = "none"

# Migration 020 seeded the stackable_with / conflicts_with arrays with informal
# aliases that do not match the canonical `programme_name` values in the same
# table ('MDEC MDAG' vs 'Malaysia Digital Acceleration Grant (MDAG)'). Without
# canonicalisation the legacy-array fallback silently matches nothing. Keys are
# lowercased; see migration 021's header for the same mapping in SQL form.
_ALIASES: dict[str, str] = {
    "mdag": "Malaysia Digital Acceleration Grant (MDAG)",
    "mdec mdag": "Malaysia Digital Acceleration Grant (MDAG)",
    "malaysia digital acceleration grant": "Malaysia Digital Acceleration Grant (MDAG)",
    "sdmg": "SME Digitalization Grant (SDMG)",
    "sme digitalization grant": "SME Digitalization Grant (SDMG)",
    "sme digitalisation grant": "SME Digitalization Grant (SDMG)",
    "mdg": "Market Development Grant (MDG)",
    "matrade mdg": "Market Development Grant (MDG)",
    "market development grant": "Market Development Grant (MDG)",
    "adf": "SME Automation & Digitalization Facility (ADF)",
    "bnm adf": "SME Automation & Digitalization Facility (ADF)",
    "cradle cip spark": "CIP Spark",
    "cradle cip sprint": "CIP Sprint",
    "hrd corp": "HRD Corp Training Fund",
    "msme digital grant": "MSME Digital Grant MADANI",
    "mtdc sandbox fund": "MTDC Sandbox Fund 4",
}


def canonical_name(name: str) -> str:
    """Fold a user-supplied or legacy-array programme name to its canonical form."""
    cleaned = " ".join((name or "").split())
    return _ALIASES.get(cleaned.lower(), cleaned)


def _pair_key(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a <= b else (b, a)


def _explanation(rule: dict[str, Any], language: str) -> str:
    if language == "bm":
        return rule.get("explanation_bm") or rule.get("explanation_en") or ""
    return rule.get("explanation_en") or rule.get("explanation_bm") or ""


async def _load_rules(supabase: Any, names: list[str]) -> Optional[list[dict[str, Any]]]:
    """Return rule rows touching any of `names`, or None if the table is
    unavailable (migration 021 not applied yet, or the query failed)."""
    try:
        res = await (
            supabase.table("grant_compatibility_rules")
            .select("*")
            .in_("programme_a", names)
            .execute()
        )
        rows_a = list(res.data or [])
        res_b = await (
            supabase.table("grant_compatibility_rules")
            .select("*")
            .in_("programme_b", names)
            .execute()
        )
        rows_b = list(res_b.data or [])
    except Exception as exc:
        log.warning("grant_compatibility_rules_unavailable", error=str(exc))
        return None

    merged: dict[Any, dict[str, Any]] = {}
    for row in rows_a + rows_b:
        merged[row.get("id") or _pair_key(
            canonical_name(row.get("programme_a", "")),
            canonical_name(row.get("programme_b", "")),
        )] = row
    return list(merged.values())


async def _load_grants(supabase: Any, names: list[str]) -> list[dict[str, Any]]:
    try:
        res = await (
            supabase.table("grant_database")
            .select("programme_name,agency,stackable_with,conflicts_with,application_url,source_url")
            .in_("programme_name", names)
            .execute()
        )
        return list(res.data or [])
    except Exception as exc:
        log.warning("grant_database_lookup_failed", error=str(exc))
        return []


def _legacy_verdict(
    grants_by_name: dict[str, dict[str, Any]], a: str, b: str
) -> tuple[str, Optional[str]]:
    """Binary verdict from the migration-020 text[] arrays. Returns
    (verdict, source_url). Never invents `partial_overlap` — the arrays
    cannot express it."""
    for first, second in ((a, b), (b, a)):
        grant = grants_by_name.get(first)
        if not grant:
            continue
        conflicts = {canonical_name(n) for n in (grant.get("conflicts_with") or [])}
        if second in conflicts:
            return CONFLICT, grant.get("source_url") or grant.get("application_url")
    for first, second in ((a, b), (b, a)):
        grant = grants_by_name.get(first)
        if not grant:
            continue
        stackable = {canonical_name(n) for n in (grant.get("stackable_with") or [])}
        if second in stackable:
            return STACKABLE, grant.get("source_url") or grant.get("application_url")
    return UNKNOWN, None


def _advice(
    language: str,
    conflict_count: int,
    partial_count: int,
    unknown_count: int,
    unrecognised: list[str],
    degraded: bool,
) -> list[str]:
    bm = language == "bm"
    out: list[str] = []
    if conflict_count:
        out.append(
            "Buang salah satu daripada setiap pasangan yang bercanggah sebelum memohon — "
            "memohon kedua-duanya boleh membatalkan permohonan."
            if bm else
            "Drop one programme from each conflicting pair before applying — "
            "submitting both can invalidate the application."
        )
    if partial_count:
        out.append(
            "Bagi pasangan bertindih separa, asingkan kos projek: setiap invois "
            "hanya boleh dituntut di bawah satu geran."
            if bm else
            "For partially overlapping pairs, split the project costs: each invoice "
            "may only be claimed under one grant."
        )
    if unknown_count:
        out.append(
            "Sesetengah pasangan belum disahkan. Jangan andaikan ia boleh ditindan — "
            "sahkan dengan agensi berkaitan sebelum memohon serentak."
            if bm else
            "Some pairs are unverified. Do not assume they stack — confirm with the "
            "relevant agencies before applying simultaneously."
        )
    if unrecognised:
        out.append(
            "Program berikut tiada dalam pangkalan data geran: " + ", ".join(unrecognised)
            if bm else
            "These programmes are not in the grant database: " + ", ".join(unrecognised)
        )
    if degraded:
        out.append(
            "Jadual peraturan keserasian belum tersedia — keputusan ini berasaskan "
            "data binari sahaja dan tidak dapat mengesan pertindihan separa."
            if bm else
            "The compatibility rules table is unavailable — this result is based on "
            "binary data only and cannot detect partial overlaps."
        )
    if not out:
        out.append(
            "Semua pasangan boleh ditindan berdasarkan rekod semasa."
            if bm else
            "All pairs are stackable based on current records."
        )
    return out


async def grant_compatibility_check(
    programme_names: list[str],
    supabase: Any,
    *,
    language: str = "en",
) -> dict[str, Any]:
    """Cross-reference `programme_names` and return a three-state matrix.

    Degrades rather than crashes: `supabase=None` or a missing
    `grant_compatibility_rules` table (migration 021 unapplied) yields
    `degraded: true` and, where possible, legacy-array verdicts.
    """
    language = "bm" if language in ("bm", "ms") else "en"

    # Canonicalise + de-duplicate while preserving caller order.
    names: list[str] = []
    for raw in programme_names:
        name = canonical_name(raw)
        if name and name not in names:
            names.append(name)

    degraded = False
    rules: list[dict[str, Any]] = []
    grants: list[dict[str, Any]] = []

    if supabase is None:
        degraded = True
    else:
        loaded = await _load_rules(supabase, names)
        if loaded is None:
            degraded = True
        else:
            rules = loaded
        grants = await _load_grants(supabase, names)

    grants_by_name = {canonical_name(g.get("programme_name", "")): g for g in grants}
    unrecognised = [n for n in names if n not in grants_by_name] if grants else []

    rules_by_pair: dict[tuple[str, str], dict[str, Any]] = {}
    for rule in rules:
        key = _pair_key(
            canonical_name(rule.get("programme_a", "")),
            canonical_name(rule.get("programme_b", "")),
        )
        rules_by_pair[key] = rule

    pairs: list[dict[str, Any]] = []
    counts = {STACKABLE: 0, PARTIAL_OVERLAP: 0, CONFLICT: 0, UNKNOWN: 0}

    for a, b in combinations(names, 2):
        key = _pair_key(a, b)
        rule = rules_by_pair.get(key)
        if rule and rule.get("rule_type") in counts:
            verdict = str(rule["rule_type"])
            entry = {
                "programme_a": key[0],
                "programme_b": key[1],
                "verdict": verdict,
                "overlap_scope": rule.get("overlap_scope"),
                "explanation": _explanation(rule, language),
                "source_url": rule.get("source_url"),
                "last_verified": str(rule["last_verified"]) if rule.get("last_verified") else None,
                "source": SOURCE_RULES_TABLE,
            }
        else:
            verdict, source_url = _legacy_verdict(grants_by_name, a, b)
            entry = {
                "programme_a": key[0],
                "programme_b": key[1],
                "verdict": verdict,
                "overlap_scope": None,
                "explanation": _fallback_explanation(verdict, language),
                "source_url": source_url,
                "last_verified": None,
                "source": SOURCE_LEGACY_ARRAY if verdict != UNKNOWN else SOURCE_NONE,
            }
        counts[entry["verdict"]] += 1
        pairs.append(entry)

    return {
        "programmes": names,
        "pairs": pairs,
        "has_conflicts": counts[CONFLICT] > 0,
        "conflict_count": counts[CONFLICT],
        "partial_overlap_count": counts[PARTIAL_OVERLAP],
        "stackable_count": counts[STACKABLE],
        "unknown_count": counts[UNKNOWN],
        "unrecognised_programmes": unrecognised,
        "degraded": degraded,
        "language": language,
        "advice": _advice(
            language,
            counts[CONFLICT],
            counts[PARTIAL_OVERLAP],
            counts[UNKNOWN],
            unrecognised,
            degraded,
        ),
    }


def _fallback_explanation(verdict: str, language: str) -> str:
    bm = language == "bm"
    if verdict == CONFLICT:
        return (
            "Direkodkan sebagai tidak serasi dalam pangkalan data geran."
            if bm else
            "Recorded as incompatible in the grant database."
        )
    if verdict == STACKABLE:
        return (
            "Direkodkan sebagai boleh ditindan dalam pangkalan data geran."
            if bm else
            "Recorded as stackable in the grant database."
        )
    return (
        "Tiada peraturan keserasian yang disahkan untuk pasangan ini. Jangan andaikan "
        "ia boleh ditindan — sahkan dengan agensi berkaitan."
        if bm else
        "No verified compatibility rule exists for this pair. Do not assume they stack — "
        "confirm with the relevant agencies."
    )
