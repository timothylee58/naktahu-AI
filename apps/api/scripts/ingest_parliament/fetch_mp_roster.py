"""
scripts/ingest_parliament/fetch_mp_roster.py

Step 0 of the "who is my MP" data path — populates the roster that
seed_mp_profiles.py upserts into mp_profiles. Nothing in this pipeline
previously sourced the 222-constituency roster itself (fetch_hansard.py /
parse_hansard.py / link_mp_profiles.py all assume mp_profiles rows already
exist and only resolve Hansard speech text to them by name).

What it does:
  1. Fetches mymp.org.my's MP directory/listing pages.
  2. Parses each MP's constituency code, constituency name, full name, party,
     and state into a normalised record.
  3. Writes data/processed/mp_roster.jsonl for seed_mp_profiles.py to consume.

NOTE (Trap #11, same caveat fetch_hansard.py already documents for
parlimen.gov.my): mymp.org.my is unreachable from this sandbox (the proxy
blocks outbound HTTPS to arbitrary sites; WebFetch/WebSearch confirmed the
domain and project are real — see scripts/sources.py's mymp-portal-home
entry — but never returned the live HTML). The CSS selectors below
(_MP_CARD_SELECTOR etc.) are a best-guess based on common civic-directory
markup, NOT verified against mymp.org.my's actual DOM. A human MUST run
this against the live site, inspect --dry-run's output, and fix the
selectors before this is trusted for a real seed. Only the pure
normalisation function (_normalise_record) is covered by unit tests here —
the same split fetch_hansard.py uses for the same reason.

Run:
  python -m scripts.ingest_parliament.fetch_mp_roster --dry-run
  python -m scripts.ingest_parliament.fetch_mp_roster
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

import httpx
import structlog
from bs4 import BeautifulSoup

_API_ROOT = Path(__file__).resolve().parents[2]
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

log = structlog.get_logger(__name__)

PROCESSED_DIR = Path(__file__).parent / "data" / "processed"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
ROSTER_FILE = PROCESSED_DIR / "mp_roster.jsonl"

MYMP_BASE = "https://mymp.org.my"
# Best guess at a listing page — unverified, see module docstring.
MYMP_LISTING_URL = "https://mymp.org.my/mp-list"

HEADERS = {
    "User-Agent": "NakTahu-Research-Bot/1.0 (Malaysian civic knowledge indexer; contact: admin@naktahu.my)",
    "Accept-Language": "en-US,en;q=0.9,ms;q=0.8",
    "Accept": "text/html,application/xhtml+xml",
}
REQUEST_DELAY_S = 1.5  # polite crawling, matching fetch_hansard.py's convention

# UNVERIFIED — see module docstring. Adjust after inspecting the live DOM.
_MP_CARD_SELECTOR = ".mp-card, .mp-list-item, article.mp"
_NAME_SELECTOR = ".mp-name, h3, h2"
_CONSTITUENCY_SELECTOR = ".mp-constituency, .constituency"
_PARTY_SELECTOR = ".mp-party, .party"
_STATE_SELECTOR = ".mp-state, .state"

_CONSTITUENCY_CODE_RE = re.compile(r"\b([A-Za-z]\.?\d{1,3})\b")


def _clean_text(el) -> str:
    return el.get_text(strip=True) if el else ""


def _normalise_record(raw: dict) -> dict | None:
    """Turn one scraped card's raw text into a validated roster record, or
    None if it's missing a required field. Pure function — the part of this
    module that IS unit-tested without a live fetch.

    Required: full_name, constituency_code, constituency_name.
    constituency_code is normalised to the same "LetterNumber" shape
    routers/parliament.py's _CONSTITUENCY_CODE_RE expects (e.g. "P.062"
    stays as-is; "p62" would need to be caught upstream — this function
    only trims/validates, it doesn't guess a malformed code into shape).
    """
    full_name = (raw.get("full_name") or "").strip()
    constituency_raw = (raw.get("constituency_raw") or "").strip()
    party = (raw.get("party") or "").strip() or None
    state = (raw.get("state") or "").strip() or None

    if not full_name or not constituency_raw:
        return None

    code_match = _CONSTITUENCY_CODE_RE.search(constituency_raw)
    if not code_match:
        return None
    constituency_code = code_match.group(1)
    # Whatever's left after removing the code is usually the readable name
    # ("P.062 Tambun" -> "Tambun"); fall back to the raw string if the code
    # was the whole field (shouldn't normally happen, but never crash on it).
    constituency_name = constituency_raw.replace(code_match.group(0), "").strip(" -–—,")
    if not constituency_name:
        constituency_name = constituency_raw

    return {
        "full_name": full_name,
        "constituency_code": constituency_code,
        "constituency_name": constituency_name,
        "party": party,
        "state": state,
        "mymp_id": raw.get("mymp_id"),
    }


def _parse_listing_html(html: str) -> list[dict]:
    """Parse the MP directory page into normalised records. Returns [] on
    any structural surprise rather than raising — a --dry-run with zero
    output is the loud, honest signal that the selectors need fixing,
    which is exactly what this module's docstring asks a human to check."""
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select(_MP_CARD_SELECTOR)
    records = []
    for card in cards:
        raw = {
            "full_name": _clean_text(card.select_one(_NAME_SELECTOR)),
            "constituency_raw": _clean_text(card.select_one(_CONSTITUENCY_SELECTOR)),
            "party": _clean_text(card.select_one(_PARTY_SELECTOR)),
            "state": _clean_text(card.select_one(_STATE_SELECTOR)),
            "mymp_id": card.get("data-id") or card.get("id"),
        }
        normalised = _normalise_record(raw)
        if normalised:
            records.append(normalised)
        else:
            log.warning("mp_roster_card_skipped", raw=raw)
    return records


async def fetch_roster(dry_run: bool) -> list[dict]:
    async with httpx.AsyncClient(headers=HEADERS, timeout=30, follow_redirects=True) as client:
        resp = await client.get(MYMP_LISTING_URL)
        resp.raise_for_status()
        await asyncio.sleep(REQUEST_DELAY_S)

    records = _parse_listing_html(resp.text)
    log.info("mp_roster_fetched", count=len(records), dry_run=dry_run)

    if not dry_run:
        with open(ROSTER_FILE, "w") as f:
            for r in records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        log.info("mp_roster_written", path=str(ROSTER_FILE))

    return records


async def main(dry_run: bool) -> None:
    records = await fetch_roster(dry_run)
    if dry_run:
        for r in records[:10]:
            print(json.dumps(r, ensure_ascii=False))
        print(f"\n{len(records)} records parsed (dry-run, nothing written).")
        if not records:
            print(
                "0 records — the selectors in this file are UNVERIFIED against "
                "the live site (see module docstring). Inspect mymp.org.my's "
                "real markup and fix _MP_CARD_SELECTOR etc. before relying on this."
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Parse and print without writing the roster file")
    args = parser.parse_args()
    asyncio.run(main(args.dry_run))
