"""Registry of listing pages the policy watcher reads.

A target is a page that LISTS new material (press statements, circulars,
announcements), not a document. Every URL here was observed in a real page by
scripts/probe_scrape_options.py run from a GitHub runner (the dev sandbox cannot
reach *.gov.my); none is guessed. `verified` records what was seen and when, so
a reader can tell a confirmed target from a candidate.

Adding a target:
  1. Find the listing page with the probe:
       python -m scripts.probe_scrape_options --url <agency home> --links 25
     (or Actions -> Scrape Probe), then probe the listing URL itself.
  2. Confirm it is USABLE and shows dated items.
  3. Dry-run the watcher on it (Actions -> Policy Watch, dry run) and read the
     sample lines: titles should be real headlines, not navigation.
  4. Append a WatchTarget below.

Not a source for ingestion: ingestion sources live in scripts/sources.py and
only get there after a human approves a queued item.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlsplit

Level = Literal["federal", "state"]


@dataclass(frozen=True)
class WatchTarget:
    name: str
    url: str
    agency: str
    level: Level
    verified: str
    notes: str = ""
    # Only links under one of these prefixes count as items (e.g. the site's
    # per-item path). Empty means any same-host link with a real title.
    item_url_prefixes: tuple[str, ...] = ()
    min_title_chars: int = 20
    # Only count links that carry a date. For listing pages whose navigation
    # menu is full of undated links, this is what separates items from chrome.
    require_date: bool = False
    # The agency's own domain. Links to any other host are ignored. Defaults to
    # the listing page's host without a leading "www.".
    host_suffix_override: str = ""

    @property
    def host_suffix(self) -> str:
        if self.host_suffix_override:
            return self.host_suffix_override
        host = urlsplit(self.url).hostname or ""
        return host[4:] if host.startswith("www.") else host


TARGETS: tuple[WatchTarget, ...] = (
    WatchTarget(
        name="hasil-media",
        url="https://www.hasil.gov.my/pengumuman-kenyataan-media/",
        agency="Lembaga Hasil Dalam Negeri (LHDN / HASiL)",
        level="federal",
        verified="Scrape Probe run 46016532521 (2026-11-27): USABLE, 97 dated items. Item links seen on the home page under /butiran-media/.",
        notes="Announcements and media statements; each item's date is printed in its link text.",
        item_url_prefixes=("https://www.hasil.gov.my/butiran-media/",),
    ),
    WatchTarget(
        name="mida-media-release",
        url="https://www.mida.gov.my/media-and-events/announcement-media-release/",
        agency="Malaysian Investment Development Authority (MIDA)",
        level="federal",
        verified="Scrape Probe run 46016532521 and the Policy Watch dry run on PR 306 (2026-11-28): item links of the form /media-release/<slug>/ with the date printed just before the link (e.g. 24 Nov 2026).",
        notes="The page is a 1.5 MB mega-menu, so only /media-release/ links that carry a date count.",
        item_url_prefixes=("https://www.mida.gov.my/media-release/",),
        require_date=True,
    ),
    WatchTarget(
        name="penang-pengumuman",
        url="https://www.penang.gov.my/index.php/pengumuman",
        agency="Kerajaan Negeri Pulau Pinang",
        level="state",
        verified="Scrape Probe run 46016532521 (2026-11-27): USABLE, 201 links. Item links seen on the home page under /index.php/pengumuman/.",
        notes="State announcements and gazette notices.",
        item_url_prefixes=("https://www.penang.gov.my/index.php/pengumuman/",),
    ),
    WatchTarget(
        name="penang-dasar-pekeliling",
        url="https://www.penang.gov.my/index.php/kerajaan/data/dasar-pekeliling",
        agency="Kerajaan Negeri Pulau Pinang",
        level="state",
        verified="Scrape Probe run 46016532521 (2026-11-27): USABLE, 296 links, 2 dated items.",
        notes="State policies and circulars; menu-heavy, so only dated links count.",
        require_date=True,
    ),
)

TARGETS_BY_NAME: dict[str, WatchTarget] = {t.name: t for t in TARGETS}
