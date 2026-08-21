"""
scripts/ingest_parliament/seed_mp_profiles.py

Upserts data/processed/mp_roster.jsonl (produced by fetch_mp_roster.py) into
the mp_profiles table (migration 025). This is the piece that was entirely
missing before: fetch_hansard.py / link_mp_profiles.py / upload_parliament.py
all assume mp_profiles rows already exist and only resolve Hansard speech
text to them by name — nothing ever populated the roster itself, so
"who is my MP for <constituency>" had no structured data to answer from even
though routers/parliament.py's read endpoints and services/parliament.py's
lookups were fully wired.

Idempotent on constituency_code (upsert, not insert) — safe to re-run after
an election or by-election without duplicating rows. Injection-scans every
free-text field before writing, matching the hard CLAUDE.md rule that no
ingestion path is exempt, even though this writes to a structured table
rather than document_chunks (a scraped full_name/constituency_name field
is exactly the kind of externally-sourced text that rule exists for).

Run:
  python -m scripts.ingest_parliament.seed_mp_profiles --dry-run
  python -m scripts.ingest_parliament.seed_mp_profiles
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

import structlog

_API_ROOT = Path(__file__).resolve().parents[2]
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

from app.middleware.sanitise import INJECTION_PATTERNS, _fold_confusables  # noqa: E402
from core.config import settings  # noqa: E402

log = structlog.get_logger(__name__)

PROCESSED_DIR = Path(__file__).parent / "data" / "processed"
ROSTER_FILE = PROCESSED_DIR / "mp_roster.jsonl"

# Same shape routers/parliament.py's _CONSTITUENCY_CODE_RE validates on read
# — a row this script writes must be findable by that endpoint later.
_CONSTITUENCY_CODE_RE = re.compile(r"^[A-Za-z]\.?\d{1,3}$")
_REQUIRED_FIELDS = ("full_name", "constituency_code", "constituency_name")


def _scan_for_injection(text: str) -> str | None:
    """Identical mechanism to ingest_feed.py / upload_parliament.py's own
    _scan_for_injection — no ingestion path is exempt (CLAUDE.md hard rule)."""
    folded = _fold_confusables(unicodedata.normalize("NFKC", text))
    for pattern in INJECTION_PATTERNS:
        if pattern.search(folded):
            return pattern.pattern
    return None


def validate_record(record: dict) -> tuple[dict, str] | tuple[None, str]:
    """Returns (cleaned_record, "") on success, or (None, reason) on
    rejection. Pure function — fully unit-testable without Supabase."""
    for field in _REQUIRED_FIELDS:
        if not (record.get(field) or "").strip():
            return None, f"missing_required_field:{field}"

    constituency_code = record["constituency_code"].strip()
    if not _CONSTITUENCY_CODE_RE.match(constituency_code):
        return None, f"invalid_constituency_code:{constituency_code}"

    free_text_fields = ("full_name", "constituency_name", "party", "state")
    for field in free_text_fields:
        value = record.get(field)
        if not value:
            continue
        matched = _scan_for_injection(str(value))
        if matched:
            return None, f"injection_suspected:{field}:{matched}"

    cleaned = {
        "full_name": record["full_name"].strip(),
        "constituency_code": constituency_code,
        "constituency_name": record["constituency_name"].strip(),
        "constituency_type": "parliament",
        "party": (record.get("party") or "").strip() or None,
        "state": (record.get("state") or "").strip() or None,
        "mymp_id": record.get("mymp_id"),
        "is_active": True,
    }
    return cleaned, ""


def load_roster(path: Path = ROSTER_FILE) -> list[dict]:
    if not path.exists():
        return []
    records = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def seed(supabase, records: list[dict], dry_run: bool) -> dict[str, int]:
    stats = {"validated": 0, "rejected": 0, "upserted": 0}
    to_upsert = []

    for record in records:
        cleaned, reason = validate_record(record)
        if cleaned is None:
            stats["rejected"] += 1
            log.warning("mp_roster_record_rejected", reason=reason, record=record)
            continue
        stats["validated"] += 1
        to_upsert.append(cleaned)

    if dry_run:
        log.info("mp_roster_seed_dry_run", would_upsert=len(to_upsert))
        for row in to_upsert[:10]:
            print(json.dumps(row, ensure_ascii=False))
        return stats

    if to_upsert:
        # Requires migration 040 (adds the UNIQUE constraint on
        # constituency_code that migration 025 didn't — the seeding
        # pipeline needing it didn't exist until this script did).
        supabase.table("mp_profiles").upsert(to_upsert, on_conflict="constituency_code").execute()
        stats["upserted"] = len(to_upsert)

    log.info("mp_roster_seed_complete", **stats)
    return stats


def main(dry_run: bool) -> int:
    records = load_roster()
    if not records:
        log.error("mp_roster_file_missing_or_empty", path=str(ROSTER_FILE))
        print(f"No roster data at {ROSTER_FILE} — run fetch_mp_roster.py first.")
        return 1

    if dry_run:
        stats = seed(None, records, dry_run=True)
    else:
        from supabase import create_client
        supabase = create_client(settings.supabase_url, settings.supabase_service_key)
        stats = seed(supabase, records, dry_run=False)

    print(json.dumps(stats))
    return 0 if stats["upserted"] > 0 or dry_run else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Validate and print without writing to Supabase")
    args = parser.parse_args()
    raise SystemExit(main(args.dry_run))
