"""Ingest Ihsan MADANI scheme records into madani_scheme.

This is a THIRD, distinct ingestion pipeline alongside the two Trap #14
already names in CLAUDE.md:
  - scripts/ingest.py       -> dosm_documents (CSV, not queried by live RAG)
  - scripts/ingest_feed.py  -> document_chunks (what rag_node's hybrid
                                search actually reads, for free-text domains)
  - scripts/ingest_madani.py (this file) -> madani_scheme (structured rows
                                WelfareEligibilityAgent's match_node filters
                                deterministically — see migration 037)

Pipeline: ingestion.sources.ihsan_madani.scraper.scrape_all() (a SEPARATE
top-level package, not under apps/api — see the subprocess note below) ->
injection scan -> eligibility_rules extraction -> build embedding text ->
embed -> diff against existing rows by source_url -> upsert.

Cross-package boundary: ingestion/ lives at the repo root, outside apps/api
(which has its own pyproject.toml / installed package set). Rather than
adding ingestion/ to apps/api's sys.path or its dependency list (which
would couple two independently-versioned packages), this script invokes
ingestion.sources.ihsan_madani.run as a SEPARATE PROCESS from the repo
root and reads back the JSON file it writes — exactly the boundary that
module's own docstring describes it exists for ("outputs clean JSON that a
separate, later step maps into madani_scheme rows"). This mirrors how
scripts/ingest_parliament/fetch_mp_roster.py and seed_mp_profiles.py are
two separate scripts bridged by a file, not one script importing the
other's internals.

Dedup/diff is keyed on source_url (not content_hash like ingest_feed.py) —
scheme descriptions can be lightly reworded on the source site without the
underlying scheme changing, so source_url is the stable identity, not an
exact-content hash.

Usage:
    python -m scripts.ingest_madani --dry-run
    python -m scripts.ingest_madani --category pendapatan kesihatan
    python -m scripts.ingest_madani   # live run, all categories
"""
from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path
from typing import Any, Optional

import structlog
from dotenv import load_dotenv
from supabase import create_client

_API_ROOT = Path(__file__).resolve().parents[1]
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))
_REPO_ROOT = _API_ROOT.parent.parent  # apps/api -> apps -> repo root (where `ingestion/` lives)

from app.middleware.sanitise import INJECTION_PATTERNS, _fold_confusables  # noqa: E402
from app.services.madani_eligibility_extraction import extract_eligibility_rules  # noqa: E402
from app.services.madani_scheme_ingest import build_scheme_embedding_text, embed_scheme  # noqa: E402
from core.config import settings  # noqa: E402

load_dotenv()

log = structlog.get_logger(__name__)


def scrape_via_subprocess(categories: Optional[list[str]] = None) -> list[dict[str, Any]]:
    """Runs the scraper in a separate process rooted at the repo root
    (where the `ingestion` package lives) and reads back its JSON output.
    Raises RuntimeError with the scraper's own stderr on failure — including
    the robots.txt-disallowed case, which run.py already reports on stderr
    and exits 1 for (see ingestion/sources/ihsan_madani/run.py)."""
    with tempfile.TemporaryDirectory() as tmp:
        out_path = Path(tmp) / "madani_schemes.json"
        cmd = [sys.executable, "-m", "ingestion.sources.ihsan_madani.run", "--out", str(out_path)]
        if categories:
            cmd += ["--category", *categories]
        result = subprocess.run(cmd, cwd=str(_REPO_ROOT), capture_output=True, text=True, timeout=1800)
        if result.returncode != 0:
            raise RuntimeError(f"ihsan_madani scraper failed: {result.stderr.strip()}")
        if not out_path.exists():
            raise RuntimeError("ihsan_madani scraper produced no output file")
        return json.loads(out_path.read_text())


def _scan_for_injection(text: str) -> Optional[str]:
    """Identical fold-then-match sequence to ingest_feed.py's
    _scan_for_injection — CLAUDE.md's rule that no ingestion path is exempt
    applies here exactly as it does to document_chunks."""
    if not text:
        return None
    folded = _fold_confusables(unicodedata.normalize("NFKC", text))
    for pattern in INJECTION_PATTERNS:
        if pattern.search(folded):
            return pattern.pattern
    return None


def _scan_scheme(record: dict[str, Any]) -> Optional[str]:
    """Scans title, description, and implementing_agency — the three
    free-text fields a scraped scheme carries that could later reach an
    LLM prompt (via build_scheme_embedding_text or the synthesiser_node
    that explains a match)."""
    for field in ("title", "description", "implementing_agency"):
        matched = _scan_for_injection(record.get(field) or "")
        if matched:
            return f"{field}: {matched}"
    return None


def _existing_rows(supabase, source_urls: list[str]) -> dict[str, dict[str, Any]]:
    if not source_urls:
        return {}
    res = (
        supabase.table("madani_scheme")
        .select("id,source_url,description,is_active,needs_review")
        .in_("source_url", source_urls)
        .execute()
    )
    return {row["source_url"]: row for row in (res.data or [])}


def _all_active_source_urls(supabase) -> set[str]:
    res = supabase.table("madani_scheme").select("id,source_url").eq("is_active", True).execute()
    return {row["source_url"] for row in (res.data or []) if row.get("source_url")}


async def _build_row(record: dict[str, Any]) -> dict[str, Any]:
    """Maps ingestion.sources.ihsan_madani.schema.MadaniScheme's field
    names (title, last_verified as scraped) onto madani_scheme's actual
    columns (scheme_name) — build_scheme_embedding_text() reads
    'scheme_name', not 'title', so this mapping has to happen before
    calling it (see that function's own module docstring)."""
    rules, confident = await extract_eligibility_rules(record["title"], record["description"])
    scheme = {
        "scheme_name": record["title"],
        "category": record["category"],
        "scope": record["scope"],
        "description": record["description"],
        "implementing_agency": record.get("implementing_agency") or "Ihsan MADANI",
        "source_url": record["source_url"],
        "aggregator_url": record.get("aggregator_url"),
        "eligibility_rules": rules,
        "needs_review": not confident,
        "is_active": True,
        "last_verified": record["last_verified"],
        "effective_date": record.get("effective_date"),
        "superseded_by": record.get("superseded_by"),
        "language": "bm",
    }
    embedding_text = build_scheme_embedding_text(scheme)
    scheme["embedding"] = await embed_scheme(scheme) if embedding_text else None
    return scheme


async def run(categories: Optional[list[str]], dry_run: bool, limit: Optional[int]) -> int:
    print("Scraping Ihsan MADANI listing pages (subprocess)...")
    try:
        records = scrape_via_subprocess(categories)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if limit:
        records = records[:limit]
    print(f"Scraped {len(records)} scheme record(s).")

    accepted: list[dict[str, Any]] = []
    rejected = 0
    for record in records:
        matched = _scan_scheme(record)
        if matched:
            rejected += 1
            log.warning(
                "madani_scheme_skipped_injection_suspected",
                title=(record.get("title") or "")[:80],
                source_url=record.get("source_url"),
                matched=matched,
            )
            continue
        accepted.append(record)

    if rejected:
        print(f"Rejected {rejected} record(s) — prompt-injection pattern suspected (see warnings above).")

    supabase = create_client(settings.supabase_url, settings.supabase_service_key)
    # "Seen this run" for the missing-on-rescrape check below uses EVERY
    # scraped record, not just the injection-accepted ones — a real,
    # still-listed scheme that happens to trip the injection filter this
    # run must not also get silently marked is_active=false; those are two
    # independent problems (content flagged vs scheme delisted) and
    # conflating them would let a false-positive injection match cascade
    # into deactivating a live scheme.
    all_scraped_urls = [r["source_url"] for r in records]
    scraped_urls = [r["source_url"] for r in accepted]
    existing_by_url = _existing_rows(supabase, scraped_urls)
    previously_active_urls = _all_active_source_urls(supabase)

    inserted = updated = unchanged = errors = 0
    for record in accepted:
        url = record["source_url"]
        existing = existing_by_url.get(url)
        if existing and existing.get("description") == record["description"] and existing.get("is_active"):
            unchanged += 1
            continue

        try:
            row = await _build_row(record)
        except Exception as exc:
            print(f"  FAILED (build/embed/extract) — {record.get('title', '')[:60]!r}: {exc}")
            errors += 1
            continue

        if dry_run:
            action = "UPDATE" if existing else "INSERT"
            review = "needs review" if row["needs_review"] else "auto-confirmed"
            print(f"  {action} (dry-run) — {row['scheme_name'][:60]!r} [{review}]")
            continue

        try:
            if existing:
                supabase.table("madani_scheme").update(row).eq("id", existing["id"]).execute()
                updated += 1
                print(f"  UPDATED — {row['scheme_name'][:60]!r}")
            else:
                supabase.table("madani_scheme").insert(row).execute()
                inserted += 1
                print(f"  INSERTED — {row['scheme_name'][:60]!r}")
        except Exception as exc:
            print(f"  FAILED (write) — {row['scheme_name'][:60]!r}: {exc}")
            errors += 1

    # Missing-on-rescrape: a previously-active row whose source_url the
    # current scrape didn't see at all. Never deleted — flipped to
    # is_active=false and surfaced loudly, since a disappearance from the
    # listing could mean the scheme genuinely ended, OR a scraper/parse
    # regression silently returned fewer records than it should have.
    # Distinguishing those two cases is a human's job, not this script's.
    missing_urls = previously_active_urls - set(all_scraped_urls)
    if missing_urls and not dry_run:
        for url in missing_urls:
            try:
                supabase.table("madani_scheme").update({"is_active": False}).eq("source_url", url).execute()
            except Exception as exc:
                print(f"  FAILED (deactivate) — {url}: {exc}")
                errors += 1
    if missing_urls:
        print(f"\n{len(missing_urls)} previously-active scheme(s) missing from this scrape "
              f"({'would be' if dry_run else ''} marked is_active=false — review before assuming they ended):")
        for url in sorted(missing_urls):
            print(f"    - {url}")

    print(f"\n{'='*60}")
    if dry_run:
        print(f"Dry-run complete — {inserted + updated} would be written, {unchanged} unchanged, "
              f"{rejected} rejected (injection), {errors} errors, {len(missing_urls)} missing-on-rescrape.")
    else:
        print(f"Ingestion complete: {inserted} inserted, {updated} updated, {unchanged} unchanged, "
              f"{rejected} rejected (injection), {errors} errors, {len(missing_urls)} deactivated (missing-on-rescrape).")
    return 1 if errors else 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest Ihsan MADANI schemes into madani_scheme")
    parser.add_argument("--category", nargs="*", default=None, help="Subset of categories (default: all)")
    parser.add_argument("--dry-run", action="store_true", help="Scrape, scan, extract, embed — do not write to Supabase")
    parser.add_argument("--limit", type=int, default=None, help="Max scraped records to process (testing)")
    args = parser.parse_args()
    sys.exit(asyncio.run(run(args.category, args.dry_run, args.limit)))


if __name__ == "__main__":
    main()
