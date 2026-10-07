"""
scripts/ingest_parliament/seed_postcode_seats.py

Loads a postcode -> parliamentary constituency crosswalk into
postcode_constituencies (migration 054), which GET
/api/v1/parliament/postcode/{postcode} joins to mp_profiles to answer
"who is the MP for my postcode".

Input is a CSV with a header row and at least these columns:

    postcode,constituency_code
    50450,P121
    50450,P122

`--source` (required) records where the data came from, e.g. the dataset's
name and version; it is stored on every row so a disputed mapping can be
traced. A postcode may appear on several rows (it can straddle seats).

Never invent rows: a wrong mapping shows a visitor the wrong MP. Rows that
are not a 5-digit postcode plus a P-code (P001-P222) are rejected and
counted, not repaired. Upserts on (postcode, constituency_code), so re-running
with a corrected file is safe; mappings removed from the file are NOT deleted
(pass --replace to delete this source's old rows first).

Run:
  python -m scripts.ingest_parliament.seed_postcode_seats \
      --csv data/raw/postcode_constituencies.csv --source "<dataset name, version>" --dry-run
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

_API_ROOT = Path(__file__).resolve().parents[2]
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

_POSTCODE_RE = re.compile(r"^\d{5}$")
_PARLIAMENT_CODE_RE = re.compile(r"^P(\d{3})$")
_BATCH = 500


def normalise_code(raw: str) -> str | None:
    """'P.121' / 'p121' / 'P121' -> 'P121'; None if not a parliamentary seat."""
    code = re.sub(r"[\s.]", "", raw or "").upper()
    m = _PARLIAMENT_CODE_RE.match(code)
    if not m or not 1 <= int(m.group(1)) <= 222:
        return None
    return code


def read_rows(path: Path, source: str) -> tuple[list[dict[str, str]], int]:
    """Valid, de-duplicated rows plus the count of rejected ones."""
    rows: dict[tuple[str, str], dict[str, str]] = {}
    rejected = 0
    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        missing = {"postcode", "constituency_code"} - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"CSV is missing column(s): {', '.join(sorted(missing))}")
        for raw in reader:
            postcode = (raw.get("postcode") or "").strip().zfill(5)
            code = normalise_code(raw.get("constituency_code") or "")
            if not _POSTCODE_RE.match(postcode) or code is None:
                rejected += 1
                continue
            rows[(postcode, code)] = {"postcode": postcode, "constituency_code": code, "source": source}
    return list(rows.values()), rejected


def upload(supabase, rows: list[dict[str, str]], source: str, replace: bool) -> int:
    if replace:
        supabase.table("postcode_constituencies").delete().eq("source", source).execute()
    for i in range(0, len(rows), _BATCH):
        supabase.table("postcode_constituencies").upsert(
            rows[i : i + _BATCH], on_conflict="postcode,constituency_code"
        ).execute()
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Load a postcode -> constituency crosswalk")
    parser.add_argument("--csv", required=True, type=Path, help="CSV with postcode,constituency_code columns")
    parser.add_argument("--source", required=True, help="Where the data came from (stored on every row)")
    parser.add_argument("--replace", action="store_true", help="Delete this source's existing rows first")
    parser.add_argument("--dry-run", action="store_true", help="Validate and report; write nothing")
    args = parser.parse_args()

    rows, rejected = read_rows(args.csv, args.source.strip())
    postcodes = len({r["postcode"] for r in rows})
    seats = len({r["constituency_code"] for r in rows})
    print(f"{len(rows)} mapping(s): {postcodes} postcode(s) across {seats} seat(s); {rejected} row(s) rejected")
    if args.dry_run or not rows:
        print("Dry run — nothing written." if args.dry_run else "Nothing to write.")
        return

    from supabase import create_client

    from core.config import settings

    supabase = create_client(settings.supabase_url, settings.supabase_service_key)
    written = upload(supabase, rows, args.source.strip(), args.replace)
    print(f"Upserted {written} mapping(s) into postcode_constituencies.")


if __name__ == "__main__":
    main()
