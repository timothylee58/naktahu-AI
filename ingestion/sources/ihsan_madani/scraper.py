"""Fetch + parse Ihsan MADANI scheme listing pages.

NOT wired into apps/api's RAG ingestion pipeline (scripts/ingest_feed.py) —
per its own module docstring, this outputs clean JSON that a separate,
later step maps into madani_scheme rows (running each through the
injection scan from app/middleware/sanitise.py, per CLAUDE.md's rule that
no ingestion path is exempt). This module never touches Supabase.

Untested against the live site: this sandbox has no egress to
ihsanmadani.gov.my — confirmed directly (curl to the site's own
robots.txt returns a 403 at the proxy tunnel, not a site response) as
recently as the same session that widened the selector fallback lists
below. The HTML selectors are therefore still best-effort placeholders
(marked TODO(verify-against-live-site)) — each field now tries a short
list of plausible Drupal 11 candidates instead of one guessed class name
(more resilient once real markup is inspected), and _parse_listing_page's
parsing LOGIC is unit-tested against a hand-written synthetic fixture
(test_scraper.py), but none of that is a substitute for someone with real
network access fetching an actual listing page, diffing its real classes
against the candidate lists, and confirming output against the live
pages before this is trusted for a real ingestion run.
"""
from __future__ import annotations

import json
import re
import time
import urllib.robotparser
from datetime import date, timezone, datetime
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

from .schema import Category, MadaniScheme

BASE_URL = "https://ihsanmadani.gov.my"
USER_AGENT = "NakTahuBot/1.0 (+https://naktahu.ai; civic AI answer engine; respectful crawl)"
REQUEST_DELAY_SECONDS = 1.5  # throttle between page fetches
REQUEST_TIMEOUT_SECONDS = 15
STATE_FILE = Path(__file__).parent / "state.json"

CATEGORIES: list[Category] = [
    "umum", "kesihatan", "makanan", "pendapatan",
    "pendidikan", "pengangkutan", "perumahan", "utiliti",
]

# Malaysia's 13 states + 3 federal territories. Matched as a title prefix
# ("Selangor: Skim ..."); anything not matching defaults to "federal" —
# never guessed beyond this fixed list.
_STATE_SLUGS = {
    "johor": "johor", "kedah": "kedah", "kelantan": "kelantan",
    "melaka": "melaka", "malacca": "melaka", "negeri sembilan": "negeri-sembilan",
    "pahang": "pahang", "perak": "perak", "perlis": "perlis",
    "pulau pinang": "pulau-pinang", "penang": "pulau-pinang",
    "sabah": "sabah", "sarawak": "sarawak", "selangor": "selangor",
    "terengganu": "terengganu",
    "kuala lumpur": "kuala-lumpur", "labuan": "labuan", "putrajaya": "putrajaya",
}


def parse_scope(title: str) -> str:
    """"Selangor: Skim Rawatan Jantung..." -> "state:selangor"; no
    recognized prefix -> "federal". Case-insensitive, prefix must be
    followed by ':' to avoid false-matching a state name mentioned
    mid-sentence.
    """
    match = re.match(r"^\s*([^:]+?)\s*:", title)
    if not match:
        return "federal"
    prefix = match.group(1).strip().lower()
    slug = _STATE_SLUGS.get(prefix)
    return f"state:{slug}" if slug else "federal"


def _robots_allows_crawl(client: httpx.Client) -> bool:
    rp = urllib.robotparser.RobotFileParser()
    try:
        resp = client.get(f"{BASE_URL}/robots.txt", timeout=REQUEST_TIMEOUT_SECONDS)
        resp.raise_for_status()
        rp.parse(resp.text.splitlines())
    except httpx.HTTPError:
        # No reachable robots.txt — fail closed, do not assume permission.
        return False
    return rp.can_fetch(USER_AGENT, f"{BASE_URL}/inisiatif/")


def _load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"last_page_by_category": {}, "seen_source_urls": []}


def _save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False))


def _first_match(card, selectors: list[str]):
    """Try each candidate selector in order, return the first hit.

    STILL UNVERIFIED AGAINST THE LIVE SITE — this sandbox has no egress to
    ihsanmadani.gov.my (confirmed: every attempt gets a 403 at the proxy
    tunnel, not a site-side response — see the module docstring). Widening
    each field to a short list of plausible Drupal 11 conventions (instead
    of one guessed class name) is a real robustness improvement for
    whoever runs this with real network access, but it is NOT a substitute
    for actually inspecting the live markup — do that before trusting any
    output this produces. TODO(verify-against-live-site) still applies to
    every list below.
    """
    for selector in selectors:
        el = card.select_one(selector)
        if el is not None:
            return el
    return None


_CARD_SELECTORS = [".views-row", "article.node--type-initiative", ".card"]  # TODO: verify
_TITLE_SELECTORS = ["h3 a", ".card-title a", "h2 a", ".node__title a"]  # TODO: verify
_DESC_SELECTORS = [".field--name-body", ".field--name-field-description", ".card-body", ".node__content"]  # TODO: verify
_AGENCY_SELECTORS = [".field--name-field-agency", ".field--name-field-implementing-agency"]  # TODO: verify


def _parse_listing_page(html: str, category: Category) -> list[MadaniScheme]:
    """Parse one category listing page into scheme records.

    TODO(verify-against-live-site): every selector list below is a
    best-effort guess at Drupal 11 conventions, not a confirmed match
    against real markup — inspect a real listing page once egress is
    available and adjust before trusting output (see module docstring and
    _first_match's docstring for why this still hasn't happened). Field
    extraction fails loudly (raises) rather than silently producing
    blank/garbage records — a scraper for a civic tool must never
    fabricate a scheme's own content.
    """
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select(", ".join(_CARD_SELECTORS))
    records: list[MadaniScheme] = []
    for card in cards:
        title_el = _first_match(card, _TITLE_SELECTORS)
        if title_el is None:
            continue
        title = title_el.get_text(strip=True)
        aggregator_url = title_el.get("href", "")
        if aggregator_url.startswith("/"):
            aggregator_url = BASE_URL + aggregator_url

        desc_el = _first_match(card, _DESC_SELECTORS)
        description = desc_el.get_text(strip=True) if desc_el else ""

        agency_el = _first_match(card, _AGENCY_SELECTORS)
        implementing_agency = agency_el.get_text(strip=True) if agency_el else None

        # "Maklumat Lanjut" ("more information") is the site's own label
        # for the primary-source link, matched by visible text rather than
        # a class name since Drupal "Read more" link markup varies more
        # than its labeling copy — still unverified (see above).
        source_link_el = card.select_one("a:-soup-contains('Maklumat Lanjut')")  # TODO: verify
        source_url = source_link_el.get("href", aggregator_url) if source_link_el else aggregator_url
        if isinstance(source_url, str) and source_url.startswith("/"):
            source_url = BASE_URL + source_url

        records.append(
            MadaniScheme(
                title=title,
                category=category,
                scope=parse_scope(title),
                description=description or title,
                implementing_agency=implementing_agency,
                source_url=source_url,
                aggregator_url=aggregator_url,
                last_verified=date.today(),
            )
        )
    return records


def scrape_category(client: httpx.Client, category: Category, state: dict) -> list[MadaniScheme]:
    """Paginate one category from its last-seen page, stopping when a
    page returns zero new (by aggregator_url) records.
    """
    seen: set[str] = set(state["seen_source_urls"])
    start_page = state["last_page_by_category"].get(category, 0)
    all_new: list[MadaniScheme] = []
    page = start_page

    while True:
        url = f"{BASE_URL}/inisiatif/{category}?page={page}"
        resp = client.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
        resp.raise_for_status()
        page_records = _parse_listing_page(resp.text, category)

        new_records = [r for r in page_records if r.aggregator_url not in seen]
        if not page_records or not new_records:
            break

        all_new.extend(new_records)
        seen.update(r.aggregator_url for r in new_records)

        state["last_page_by_category"][category] = page
        state["seen_source_urls"] = sorted(seen)
        _save_state(state)

        page += 1
        time.sleep(REQUEST_DELAY_SECONDS)

    return all_new


def scrape_all(categories: list[Category] | None = None) -> list[MadaniScheme]:
    categories = categories or CATEGORIES
    state = _load_state()
    headers = {"User-Agent": USER_AGENT}

    with httpx.Client(headers=headers, follow_redirects=True) as client:
        if not _robots_allows_crawl(client):
            raise RuntimeError(
                f"robots.txt disallows {USER_AGENT} on {BASE_URL}/inisiatif/ "
                "— refusing to crawl. Check manually before overriding."
            )

        results: list[MadaniScheme] = []
        for category in categories:
            results.extend(scrape_category(client, category, state))
            time.sleep(REQUEST_DELAY_SECONDS)

    return results
