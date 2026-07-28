"""
scripts/ingest_parliament/fetch_hansard.py

Step 1 of the Hansard ingestion pipeline.
Discovers and downloads Hansard PDFs from parlimen.gov.my.

What it does:
  1. Scrapes the Hansard listing page for Dewan Rakyat sittings.
  2. Identifies new sittings not yet in hansard_sittings table.
  3. Downloads PDFs to scripts/ingest_parliament/data/raw/hansard/.
  4. Inserts sitting records into hansard_sittings (ingested=false).

Run: python -m scripts.ingest_parliament.fetch_hansard [--year 2025]

Output:
  data/raw/hansard/YYYY-MM-DD_DR.pdf per sitting
  data/raw/hansard/manifest.jsonl — one JSON record per sitting

NOTE (Trap #11): parlimen.gov.my is unreachable from this sandbox (proxy
blocks outbound HTTPS to arbitrary government sites, as it did for the MIDA
InvestMalaysia sources ingest_feed.py was written for). The scraping logic
below has NOT been exercised against the live site in this session — only
the pure functions (_parse_date_from_filename, _parse_date_from_text) are
covered by unit tests here. A human must run this against the live site to
confirm the CSS/tag selectors still match parlimen.gov.my's current markup
before the Railway cron is trusted unattended.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from datetime import date
from pathlib import Path

import httpx
import structlog
from bs4 import BeautifulSoup
from supabase import create_client

# apps/api root — scripts/ingest_parliament/fetch_hansard.py -> parents[2] == apps/api
_API_ROOT = Path(__file__).resolve().parents[2]
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

from core.config import settings  # noqa: E402

log = structlog.get_logger(__name__)

RAW_DIR = Path(__file__).parent / "data" / "raw" / "hansard"
RAW_DIR.mkdir(parents=True, exist_ok=True)
MANIFEST = RAW_DIR / "manifest.jsonl"

# parlimen.gov.my Hansard index pages
HANSARD_BASE = "https://www.parlimen.gov.my"
HANSARD_LIST_URL = "https://www.parlimen.gov.my/hansard-dewan-rakyat.html"

# Polite scraping headers — identify as a research bot
HEADERS = {
    "User-Agent": "NakTahu-Research-Bot/1.0 (Malaysian civic knowledge indexer; contact: admin@naktahu.my)",
    "Accept-Language": "en-US,en;q=0.9,ms;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/pdf",
}
REQUEST_DELAY_S = 2.0  # seconds between requests — polite crawling


def _parse_date_from_filename(filename: str) -> date | None:
    """Extract date from parlimen.gov.my PDF filenames like DR-07072025.pdf."""
    patterns = [
        r"DR[_\-](\d{2})(\d{2})(\d{4})",  # DR-07072025
        r"(\d{4})-(\d{2})-(\d{2})",       # 2025-07-07
        r"(\d{2})-(\d{2})-(\d{4})",       # 07-07-2025
    ]
    for pattern in patterns:
        match = re.search(pattern, filename, re.IGNORECASE)
        if match:
            groups = match.groups()
            try:
                if len(groups[0]) == 4:      # YYYY-MM-DD
                    return date(int(groups[0]), int(groups[1]), int(groups[2]))
                elif len(groups[2]) == 4:    # DD-MM-YYYY or DDMMYYYY
                    return date(int(groups[2]), int(groups[1]), int(groups[0]))
            except ValueError:
                continue
    return None


_MONTHS_EN = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
_MONTHS_BM = {
    "jan": 1, "feb": 2, "mac": 3, "apr": 4, "mei": 5, "jun": 6,
    "jul": 7, "ogo": 8, "sep": 9, "okt": 10, "nov": 11, "dis": 12,
}
_MONTHS = {**_MONTHS_EN, **_MONTHS_BM}


def _parse_date_from_text(text: str) -> date | None:
    """Parse date from display text like '24 Jun 2025' or '7 Julai 2025'."""
    text = text.lower().strip()
    match = re.search(r"(\d{1,2})\s+([a-z]+)\s+(\d{4})", text)
    if match:
        day, mon_str, year = int(match.group(1)), match.group(2)[:3], int(match.group(3))
        month = _MONTHS.get(mon_str)
        if month:
            try:
                return date(year, month, day)
            except ValueError:
                pass
    return None


def _make_sitting_id(sitting_date: date, chamber: str = "DR") -> str:
    """Generate a stable sitting ID: e.g. DR.2025-07-07"""
    return f"{chamber}.{sitting_date.isoformat()}"


def _estimate_parliament(d: date) -> int:
    """Estimate parliament number from date (Malaysia GE history)."""
    if d >= date(2023, 11, 19):
        return 15
    if d >= date(2018, 7, 16):
        return 14
    return 13


def _estimate_session(d: date) -> int:
    """Very rough session estimate — overridden by actual Hansard data."""
    return d.year - 2022 if d.year >= 2022 else 1


async def _fetch_sitting_list(year: int | None = None) -> list[dict]:
    """
    Scrape the Hansard listing page and return a list of sitting dicts.
    Each dict: {sitting_id, sitting_date, pdf_url, chamber, parliament_no, session_no}
    """
    sittings: list[dict] = []

    async with httpx.AsyncClient(headers=HEADERS, timeout=30, follow_redirects=True) as client:
        resp = await client.get(HANSARD_LIST_URL)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        pdf_links = soup.find_all("a", href=re.compile(r"\.pdf$", re.IGNORECASE))
        log.info("hansard_links_found", count=len(pdf_links))

        for link in pdf_links:
            href = link.get("href", "")
            if not href:
                continue

            if href.startswith("/"):
                href = HANSARD_BASE + href
            elif not href.startswith("http"):
                href = HANSARD_BASE + "/" + href

            filename = href.split("/")[-1]
            sitting_date = _parse_date_from_filename(filename)

            if not sitting_date:
                link_text = link.get_text(strip=True)
                sitting_date = _parse_date_from_text(link_text)

            if not sitting_date:
                log.warning("cannot_parse_date", filename=filename)
                continue

            if year and sitting_date.year != year:
                continue
            if sitting_date.year < 2020:
                continue

            sitting_id = _make_sitting_id(sitting_date)
            sittings.append({
                "sitting_id":    sitting_id,
                "sitting_date":  sitting_date.isoformat(),
                "pdf_url":       href,
                "chamber":       "dewan_rakyat",
                "parliament_no": _estimate_parliament(sitting_date),
                "session_no":    _estimate_session(sitting_date),
            })

        seen = set()
        unique = []
        for s in sittings:
            if s["sitting_id"] not in seen:
                seen.add(s["sitting_id"])
                unique.append(s)

    log.info("hansard_sittings_found", total=len(unique), year=year)
    return sorted(unique, key=lambda s: s["sitting_date"], reverse=True)


async def _download_pdf(client: httpx.AsyncClient, url: str, dest: Path) -> bool:
    """Download a PDF if not already cached. Returns True on success."""
    if dest.exists() and dest.stat().st_size > 10_000:
        return True
    try:
        resp = await client.get(url, timeout=60)
        resp.raise_for_status()
        dest.write_bytes(resp.content)
        log.info("pdf_downloaded", url=url, size_kb=len(resp.content) // 1024)
        return True
    except Exception as exc:
        log.error("pdf_download_failed", url=url, error=str(exc))
        return False


async def main(year: int | None = None, dry_run: bool = False) -> None:
    supabase = None if dry_run else create_client(settings.supabase_url, settings.supabase_service_key)

    existing_ids: set[str] = set()
    if supabase is not None:
        existing = supabase.table("hansard_sittings").select("sitting_id").execute()
        existing_ids = {row["sitting_id"] for row in (existing.data or [])}
        log.info("existing_sittings", count=len(existing_ids))

    sittings = await _fetch_sitting_list(year)
    new_sittings = [s for s in sittings if s["sitting_id"] not in existing_ids]
    log.info("new_sittings", count=len(new_sittings))

    if dry_run:
        for s in new_sittings:
            print(json.dumps(s))
        return

    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True) as client:
        for s in new_sittings:
            dest = RAW_DIR / f"{s['sitting_date']}_DR.pdf"
            success = await _download_pdf(client, s["pdf_url"], dest)

            if success:
                supabase.table("hansard_sittings").insert({
                    **s,
                    "ingested": False,
                }).execute()
                log.info("sitting_registered", sitting_id=s["sitting_id"])

                with open(MANIFEST, "a") as f:
                    f.write(json.dumps({**s, "local_path": str(dest)}) + "\n")

            await asyncio.sleep(REQUEST_DELAY_S)

    log.info("fetch_complete", total_new=len(new_sittings))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(args.year, args.dry_run))
