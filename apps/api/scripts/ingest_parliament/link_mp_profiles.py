"""
scripts/ingest_parliament/link_mp_profiles.py

Step 3 of the Hansard ingestion pipeline.
Resolves extracted MP names from parse_hansard.py to mp_profiles table rows.

The challenge: Hansard text uses inconsistent name formats:
  "YB GOBIND SINGH DEO"
  "YAB Dato' Sri Anwar Ibrahim"
  "YB Tuan [Name] [Constituency]"
  "DR. XAVIER JAYAKUMAR"

Strategy (each resolved name is tagged with which one fired, since this
pipeline attributes real speech and real votes to real, named Malaysian
politicians and that provenance must not be invisible downstream):
  1. exact  — exact normalised full-name match (confidence 1.0).
  2. constituency_code — disambiguation/resolution via P.NNN code
     (confidence 0.9).
  3. fuzzy  — token-overlap >=0.65 (confidence == the overlap score, always
     < 1.0). Lowest-trust tier; surfaced distinctly by upload_parliament.py.
  4. Unresolved names go to unresolved_names.jsonl for manual review.

Output:
  data/processed/mp_name_lookup.json — {extracted_name: {mp_id, confidence, strategy}}
  data/processed/unresolved_names.jsonl — names that couldn't be resolved

Run: python -m scripts.ingest_parliament.link_mp_profiles
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

import structlog

_API_ROOT = Path(__file__).resolve().parents[2]
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

from core.config import settings  # noqa: E402

log = structlog.get_logger(__name__)

PROCESSED_DIR = Path(__file__).parent / "data" / "processed"
LOOKUP_OUT = PROCESSED_DIR / "mp_name_lookup.json"
UNRESOLVED_OUT = PROCESSED_DIR / "unresolved_names.jsonl"

FUZZY_THRESHOLD = 0.65

_TITLES = [
    "yb", "yab", "ybhg", "dato'", "dato", "datuk", "tan sri", "tun",
    "dr", "dr.", "mr", "mrs", "ms", "prof", "haji", "hajah", "ir",
]


def _normalise(name: str) -> str:
    """Normalise a name for fuzzy matching. Strips titles, accents,
    punctuation, lowercases."""
    name_lower = name.lower().strip()
    for t in _TITLES:
        name_lower = re.sub(rf"^{re.escape(t)}\s+", "", name_lower)
        name_lower = name_lower.replace(f" {t} ", " ")

    name_lower = unicodedata.normalize("NFKD", name_lower)
    name_lower = "".join(c for c in name_lower if not unicodedata.combining(c))

    name_lower = re.sub(r"[^\w\s-]", "", name_lower)
    name_lower = re.sub(r"\s+", " ", name_lower).strip()
    return name_lower


def _token_overlap(a: str, b: str) -> float:
    """0.0-1.0 overlap score between two normalised name strings."""
    tokens_a = set(a.split())
    tokens_b = set(b.split())
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)


def build_lookup(
    extracted_names: list[tuple[str, str | None]],  # (name, constituency_code_hint)
    mp_rows: list[dict],
) -> tuple[dict[str, dict], list[dict]]:
    """
    Build {extracted_name: {mp_id, confidence, strategy}} lookup dict.
    Returns (lookup, unresolved_list).
    """
    mp_index = [
        {
            "id": row["id"],
            "full_name": row["full_name"],
            "norm_name": _normalise(row["full_name"]),
            "const_code": row.get("constituency_code", "") or "",
        }
        for row in mp_rows
    ]

    lookup: dict[str, dict] = {}
    unresolved: list[dict] = []

    for raw_name, const_hint in extracted_names:
        if raw_name in lookup:
            continue

        norm = _normalise(raw_name)

        # Strategy 1: exact normalised name match
        exact = [m for m in mp_index if m["norm_name"] == norm]
        if len(exact) == 1:
            lookup[raw_name] = {"mp_id": exact[0]["id"], "confidence": 1.0, "strategy": "exact"}
            continue
        if len(exact) > 1 and const_hint:
            const_code = re.search(r"P\.?\d{3}", const_hint or "")
            if const_code:
                filtered = [m for m in exact if const_code.group(0).replace(".", "") in m["const_code"]]
                if filtered:
                    lookup[raw_name] = {
                        "mp_id": filtered[0]["id"],
                        "confidence": 0.95,
                        "strategy": "constituency_code",
                    }
                    continue

        # Strategy 2: constituency code match
        if const_hint:
            code_match = re.search(r"(P\.?\d{3})", const_hint)
            if code_match:
                clean_code = code_match.group(1).replace(".", "")
                by_const = [
                    m for m in mp_rows
                    if (m.get("constituency_code") or "").replace(".", "") == clean_code
                ]
                if len(by_const) == 1:
                    lookup[raw_name] = {
                        "mp_id": by_const[0]["id"],
                        "confidence": 0.9,
                        "strategy": "constituency_code",
                    }
                    continue

        # Strategy 3: fuzzy token overlap
        scores = [(m["id"], _token_overlap(norm, m["norm_name"])) for m in mp_index]
        if scores:
            best_id, best_score = max(scores, key=lambda x: x[1])
        else:
            best_id, best_score = None, 0.0
        if best_score >= FUZZY_THRESHOLD:
            lookup[raw_name] = {"mp_id": best_id, "confidence": round(best_score, 2), "strategy": "fuzzy"}
            log.debug("fuzzy_match", name=raw_name, score=round(best_score, 2))
            continue

        unresolved.append({
            "raw_name": raw_name,
            "const_hint": const_hint,
            "best_score": round(best_score, 2),
            "closest_mp": next((m["full_name"] for m in mp_index if m["id"] == best_id), ""),
        })

    return lookup, unresolved


def main() -> None:
    from supabase import create_client

    supabase = create_client(settings.supabase_url, settings.supabase_service_key)

    mp_resp = supabase.table("mp_profiles").select("id,full_name,constituency_code").execute()
    mp_rows = mp_resp.data or []
    log.info("mp_profiles_loaded", count=len(mp_rows))

    statements_path = PROCESSED_DIR / "hansard_statements.jsonl"
    if not statements_path.exists():
        log.error("statements_not_found", path=str(statements_path))
        return

    name_set: dict[str, str | None] = {}
    with open(statements_path) as f:
        for line in f:
            s = json.loads(line)
            name = s.get("mp_name", "")
            if name:
                name_set[name] = s.get("constituency_code")

    log.info("unique_names_to_resolve", count=len(name_set))

    lookup, unresolved = build_lookup(
        [(name, code) for name, code in name_set.items()],
        mp_rows,
    )

    with open(LOOKUP_OUT, "w") as f:
        json.dump(lookup, f, indent=2)

    with open(UNRESOLVED_OUT, "w") as f:
        for u in unresolved:
            f.write(json.dumps(u) + "\n")

    fuzzy_count = sum(1 for v in lookup.values() if v["strategy"] == "fuzzy")
    log.info(
        "linking_complete",
        resolved=len(lookup),
        resolved_fuzzy_low_confidence=fuzzy_count,
        unresolved=len(unresolved),
        resolution_rate=f"{len(lookup) / max(len(name_set), 1):.0%}",
    )


if __name__ == "__main__":
    main()
