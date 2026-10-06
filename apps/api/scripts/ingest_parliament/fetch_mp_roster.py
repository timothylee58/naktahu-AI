"""
scripts/ingest_parliament/fetch_mp_roster.py

Step 0 of the "who is my MP" data path — populates the roster that
seed_mp_profiles.py upserts into mp_profiles. Nothing in this pipeline
previously sourced the 222-constituency roster itself (fetch_hansard.py /
parse_hansard.py / link_mp_profiles.py all assume mp_profiles rows already
exist and only resolve Hansard speech text to them by name).

What it does:
  1. Fetches mymp.org.my's politician sitemap (/politicians/sitemap), a flat
     list of links to every MP's profile page (/p/<slug>).
  2. Fetches each profile and reads the seat code, seat name, MP's name and
     party from the profile header.
  3. Derives the state from the seat code (P001-P222 are numbered by state
     and the ranges are fixed by the Federal Constitution's delimitation).
  4. Writes data/processed/mp_roster.jsonl for seed_mp_profiles.py to consume.

Selectors were checked against the live site on 2026-10-07. The profile
header looks like:

    <p ...><span class="text-primary">P137</span>
       <span class="text-constituency font-weight-bold">HANG TUAH JAYA</span></p>
    <h2 class="p-name ..."><p class="mb-1">Adam Adli Abd Halim</p>
       <p class="badge ...">Parti Keadilan Rakyat (PKR)</p></h2>

Seat codes are stored as "P137" — the exact shape seed_postcode_seats.py
writes into postcode_constituencies, because services/parliament.py joins
the two tables on an exact constituency_code match.

If the sitemap ever lists two profiles for one seat (e.g. a by-election
winner alongside the previous MP), the run refuses to write the file and
prints the clashes: picking one would be a guess, and a wrong guess shows a
visitor the wrong MP.

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
MYMP_SITEMAP_URL = f"{MYMP_BASE}/politicians/sitemap"

HEADERS = {
    "User-Agent": "NakTahu-Research-Bot/1.0 (Malaysian civic knowledge indexer; contact: admin@naktahu.my)",
    "Accept-Language": "en-US,en;q=0.9,ms;q=0.8",
    "Accept": "text/html,application/xhtml+xml",
}
REQUEST_DELAY_S = 1.5  # polite crawling, matching fetch_hansard.py's convention

_PROFILE_HREF_RE = re.compile(r"^(?:https://mymp\.org\.my)?/p/([a-z0-9-]+)/?$")
_SEAT_CODE_RE = re.compile(r"\bP\.?\s?(\d{1,3})\b", re.IGNORECASE)

# Parliamentary seat numbering by state (inclusive ranges). Fixed since the
# 2003 delimitation; the 2018 Selangor redelineation kept the seat count.
_STATE_BY_SEAT_RANGE: tuple[tuple[int, int, str], ...] = (
    (1, 3, "Perlis"),
    (4, 18, "Kedah"),
    (19, 32, "Kelantan"),
    (33, 40, "Terengganu"),
    (41, 53, "Pulau Pinang"),
    (54, 77, "Perak"),
    (78, 91, "Pahang"),
    (92, 113, "Selangor"),
    (114, 124, "Wilayah Persekutuan Kuala Lumpur"),
    (125, 125, "Wilayah Persekutuan Putrajaya"),
    (126, 133, "Negeri Sembilan"),
    (134, 139, "Melaka"),
    (140, 165, "Johor"),
    (166, 166, "Wilayah Persekutuan Labuan"),
    (167, 191, "Sabah"),
    (192, 222, "Sarawak"),
)


def _clean_text(el) -> str:
    return " ".join(el.get_text(" ", strip=True).split()) if el else ""


def normalise_seat_code(raw: str) -> str | None:
    """'P.062' / 'p62' / 'P062' -> 'P062'; None if not P001-P222."""
    m = _SEAT_CODE_RE.search(raw or "")
    if not m or not 1 <= int(m.group(1)) <= 222:
        return None
    return f"P{int(m.group(1)):03d}"


def state_for_seat(code: str) -> str | None:
    n = int(code[1:])
    for lo, hi, state in _STATE_BY_SEAT_RANGE:
        if lo <= n <= hi:
            return state
    return None


def _normalise_record(raw: dict) -> dict | None:
    """Turn one profile's raw text into a validated roster record, or None
    if it's missing a required field. Pure function — unit-tested without a
    live fetch.

    Required: full_name, and a constituency_raw containing a P-code. The
    seat name comes from constituency_name when the page gives it
    separately, else from whatever surrounds the code in constituency_raw.
    """
    full_name = (raw.get("full_name") or "").strip()
    constituency_raw = (raw.get("constituency_raw") or "").strip()
    party = (raw.get("party") or "").strip() or None

    if not full_name or not constituency_raw:
        return None

    constituency_code = normalise_seat_code(constituency_raw)
    if constituency_code is None:
        return None

    constituency_name = (raw.get("constituency_name") or "").strip()
    if not constituency_name:
        constituency_name = _SEAT_CODE_RE.sub("", constituency_raw).strip(" -–—,")
    if not constituency_name:
        constituency_name = constituency_code

    return {
        "full_name": full_name,
        "constituency_code": constituency_code,
        "constituency_name": constituency_name.title(),
        "party": party,
        "state": (raw.get("state") or "").strip() or state_for_seat(constituency_code),
        "mymp_id": raw.get("mymp_id"),
    }


def _parse_sitemap_html(html: str) -> list[str]:
    """Profile slugs from /politicians/sitemap, de-duplicated, in page order."""
    soup = BeautifulSoup(html, "html.parser")
    slugs: dict[str, None] = {}
    for a in soup.find_all("a", href=True):
        m = _PROFILE_HREF_RE.match(a["href"].strip())
        if m:
            slugs[m.group(1)] = None
    return list(slugs)


def _parse_profile_html(html: str, slug: str) -> dict | None:
    """One profile page -> roster record, or None (logged) if the page
    doesn't carry a seat code — e.g. a former MP with no current seat."""
    soup = BeautifulSoup(html, "html.parser")
    code_el = soup.select_one("span.text-primary")
    seat_el = soup.select_one("span.text-constituency")
    name_el = soup.select_one("h2.p-name p.mb-1")
    party_el = soup.select_one("h2.p-name .badge")
    raw = {
        "full_name": _clean_text(name_el),
        "constituency_raw": _clean_text(code_el),
        "constituency_name": _clean_text(seat_el),
        "party": _clean_text(party_el),
        "mymp_id": slug,
    }
    record = _normalise_record(raw)
    if record is None:
        log.warning("mp_roster_profile_skipped", slug=slug, raw=raw)
    return record


def find_seat_clashes(records: list[dict]) -> dict[str, list[str]]:
    """Seat code -> profile slugs, for every seat claimed by more than one."""
    by_seat: dict[str, list[str]] = {}
    for r in records:
        by_seat.setdefault(r["constituency_code"], []).append(r["mymp_id"])
    return {code: slugs for code, slugs in by_seat.items() if len(slugs) > 1}


async def fetch_roster() -> list[dict]:
    records: list[dict] = []
    async with httpx.AsyncClient(headers=HEADERS, timeout=30, follow_redirects=True) as client:
        resp = await client.get(MYMP_SITEMAP_URL)
        resp.raise_for_status()
        slugs = _parse_sitemap_html(resp.text)
        log.info("mp_roster_sitemap_fetched", profiles=len(slugs))

        for i, slug in enumerate(slugs, 1):
            await asyncio.sleep(REQUEST_DELAY_S)
            try:
                page = await client.get(f"{MYMP_BASE}/p/{slug}")
                page.raise_for_status()
            except httpx.HTTPError as exc:
                log.warning("mp_roster_profile_fetch_failed", slug=slug, error=str(exc)[:200])
                continue
            record = _parse_profile_html(page.text, slug)
            if record:
                records.append(record)
            if i % 25 == 0:
                log.info("mp_roster_progress", fetched=i, of=len(slugs))

    return sorted(records, key=lambda r: r["constituency_code"])


async def main(dry_run: bool) -> int:
    records = await fetch_roster()
    seats = {r["constituency_code"] for r in records}
    missing = [f"P{n:03d}" for n in range(1, 223) if f"P{n:03d}" not in seats]
    clashes = find_seat_clashes(records)

    print(f"{len(records)} profiles parsed, covering {len(seats)} of 222 seats.")
    if missing:
        print(f"Seats with no MP profile ({len(missing)}): {', '.join(missing)}")
    if clashes:
        print("Seats claimed by more than one profile — resolve before seeding:")
        for code, slugs in sorted(clashes.items()):
            print(f"  {code}: {', '.join(slugs)}")
        return 1

    if dry_run:
        for r in records[:10]:
            print(json.dumps(r, ensure_ascii=False))
        print("(dry-run, nothing written)")
        return 0

    with open(ROSTER_FILE, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    log.info("mp_roster_written", path=str(ROSTER_FILE), count=len(records))
    print(f"Wrote {ROSTER_FILE}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Fetch and parse without writing the roster file")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(args.dry_run)))
