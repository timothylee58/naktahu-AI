#!/usr/bin/env python3
"""Sandbox for comparing ways to fetch a Malaysian government page.

Answers one question per option: given the same URL, what do we actually get
back, and would the existing ingestion path (parse_html_page + injection scan)
find usable text in it? Writes nothing: no Supabase, no embeddings, no
document_chunks. Safe to run anywhere.

Why this exists: the dev sandbox blocks outbound HTTPS to *.gov.my at the
egress proxy, so none of these options could be judged from here. Run it from a
GitHub Actions runner (see .github/workflows/scrape-probe.yml), which has normal
internet access, or from your own machine.

Usage (from apps/api):

    python -m scripts.probe_scrape_options                       # DOSM, free option only
    python -m scripts.probe_scrape_options --source dosm-portal-home
    python -m scripts.probe_scrape_options --url https://www.dosm.gov.my/
    python -m scripts.probe_scrape_options --url https://www.moh.gov.my/ --links 25   # find listing pages
    EXA_API_KEY=... BRIGHTDATA_API_KEY=... BRIGHTDATA_ZONE=... \\
        python -m scripts.probe_scrape_options --include-paid --json-out probe.json

Options compared:
  httpx        free; the same fetch ingest_feed.py uses. Always runs.
  exa          paid search/contents API; needs EXA_API_KEY and --include-paid.
  brightdata   paid unblocker proxy; needs BRIGHTDATA_API_KEY, BRIGHTDATA_ZONE
               and --include-paid.
Not automated (need an interactive session, so judge them by hand): Kernel cloud
browser for JavaScript-rendered pages, and the built-in WebSearch for finding
candidate URLs. The paid endpoints below follow each vendor's documented
request shape but were never called from this repo: a non-200 is reported as
ERROR, never read as "the site is unscrapable".

Verdicts:
  USABLE    the page parsed into real text the ingester could chunk
  THIN      200 OK but almost no text: usually a JavaScript shell or a block page
  BLOCKED   the host refused us (401/403/429, or a bot-challenge page)
  ERROR     network or API failure; says nothing about the site
  SKIPPED   option not configured
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import urldefrag, urljoin, urlsplit

import httpx

_API_ROOT = Path(__file__).resolve().parents[1]
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

from scripts.ingest_feed import _host_in_domain, _scan_for_injection, parse_html_page  # noqa: E402
from scripts.sources import SOURCES_BY_NAME  # noqa: E402

DEFAULT_SOURCES = ("dosm-portal-home", "opendosm-home")
ALLOWED_DOMAIN = "gov.my"
_TIMEOUT = httpx.Timeout(45.0, connect=15.0)
_USER_AGENT = "NakTahu-ScrapeProbe/1.0"
_MIN_USABLE_CHARS = 500
_BLOCK_STATUSES = frozenset({401, 403, 429})
_CHALLENGE_MARKERS = ("just a moment", "attention required", "access denied", "captcha", "cf-chl")
_DATE_RE = re.compile(
    r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{4}|\d{4}-\d{2}-\d{2}|\d{1,2}\s+"
    r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|mac|mei|ogo|okt|dis)[a-z]*\.?\s+\d{4})\b",
    re.IGNORECASE,
)
_LINK_RE = re.compile(r"<a\s[^>]*href=", re.IGNORECASE)
_SCRIPT_RE = re.compile(r"<script\b", re.IGNORECASE)


# Words that mark a link as a place where new policy material is published.
_LISTING_HINTS = (
    "media", "berita", "news", "kenyataan", "statement", "press", "pekeliling", "circular",
    "pengumuman", "announcement", "terbitan", "penerbitan", "publication", "release",
    "dasar", "polic", "garis-panduan", "guideline", "arkib", "archive", "notis", "notice",
)
_MAX_LINK_TEXT = 120


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._href: Optional[str] = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        if tag == "a":
            self._href = dict(attrs).get("href")
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._href is not None:
            self.links.append((self._href, " ".join("".join(self._text).split())))
            self._href = None


def extract_links(html: str, base_url: str) -> list[dict[str, str]]:
    """Absolute, de-duplicated links that stay under *.gov.my. Off-domain and
    non-http links are dropped here so nothing downstream can be pointed at them."""
    parser = _LinkParser()
    parser.feed(html)
    seen: set[str] = set()
    links: list[dict[str, str]] = []
    for href, text in parser.links:
        absolute, _ = urldefrag(urljoin(base_url, href.strip()))
        parts = urlsplit(absolute)
        if parts.scheme not in ("http", "https") or not parts.hostname or not _host_in_domain(parts.hostname, ALLOWED_DOMAIN):
            continue
        if absolute in seen:
            continue
        seen.add(absolute)
        links.append({"url": absolute, "text": text[:_MAX_LINK_TEXT]})
    return links


def listing_candidates(links: list[dict[str, str]], limit: int) -> list[dict[str, str]]:
    """Links whose address or label suggests a listing of new material, best first."""
    scored: list[tuple[int, dict[str, str]]] = []
    for link in links:
        haystack = f"{link['url']} {link['text']}".lower()
        score = sum(1 for hint in _LISTING_HINTS if hint in haystack)
        if score:
            scored.append((score, link))
    scored.sort(key=lambda pair: -pair[0])
    return [link for _, link in scored[:limit]]


@dataclass
class Fetched:
    status: Optional[int]
    body: bytes
    seconds: float
    error: Optional[str] = None
    off_domain_hosts: list[str] = field(default_factory=list)


@dataclass
class Result:
    option: str
    url: str
    verdict: str
    detail: str
    status: Optional[int] = None
    seconds: float = 0.0
    text_chars: int = 0
    chunks: int = 0
    links: int = 0
    dated_items: int = 0
    scripts: int = 0
    injection_pattern: Optional[str] = None
    title: str = ""
    listing_links: list[dict[str, str]] = field(default_factory=list)


def validate_target(url: str, domain: str = ALLOWED_DOMAIN) -> str:
    """https only, and only under `domain`. Paid proxies fetch whatever they are
    told to, so the guard sits here, before any option is called."""
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname or not _host_in_domain(parts.hostname, domain):
        raise ValueError(f"{url!r} is not an https URL under *.{domain}")
    return url


def fetch_httpx(url: str, client: httpx.Client) -> Fetched:
    start = time.monotonic()
    try:
        resp = client.get(url, headers={"User-Agent": _USER_AGENT}, follow_redirects=True)
    except httpx.HTTPError as exc:
        return Fetched(None, b"", time.monotonic() - start, error=f"{type(exc).__name__}: {str(exc)[:120]}")
    hosts = [r.url.host for r in resp.history] + [resp.url.host]
    stray = sorted({h for h in hosts if not _host_in_domain(h, ALLOWED_DOMAIN)})
    return Fetched(resp.status_code, resp.content, time.monotonic() - start, off_domain_hosts=stray)


def fetch_exa(url: str, client: httpx.Client, api_key: str) -> Fetched:
    start = time.monotonic()
    try:
        resp = client.post(
            "https://api.exa.ai/contents",
            headers={"x-api-key": api_key, "content-type": "application/json"},
            json={"urls": [url], "text": True},
        )
        payload = resp.json() if resp.status_code == 200 else {}
    except (httpx.HTTPError, ValueError) as exc:
        return Fetched(None, b"", time.monotonic() - start, error=f"{type(exc).__name__}: {str(exc)[:120]}")
    if resp.status_code != 200:
        return Fetched(resp.status_code, b"", time.monotonic() - start, error=f"exa returned {resp.status_code}")
    results = payload.get("results") or []
    text = (results[0].get("text") if results else "") or ""
    # Exa returns extracted text, not HTML: wrap it so the shared parser sees paragraphs.
    html = "<html><body>" + "".join(f"<p>{line}</p>" for line in text.splitlines() if line.strip()) + "</body></html>"
    return Fetched(200, html.encode("utf-8"), time.monotonic() - start)


def fetch_brightdata(url: str, client: httpx.Client, api_key: str, zone: str) -> Fetched:
    start = time.monotonic()
    try:
        resp = client.post(
            "https://api.brightdata.com/request",
            headers={"Authorization": f"Bearer {api_key}", "content-type": "application/json"},
            json={"zone": zone, "url": url, "format": "raw"},
        )
    except httpx.HTTPError as exc:
        return Fetched(None, b"", time.monotonic() - start, error=f"{type(exc).__name__}: {str(exc)[:120]}")
    return Fetched(resp.status_code, resp.content, time.monotonic() - start)


def analyse(option: str, url: str, fetched: Fetched, link_limit: int = 0) -> Result:
    base = Result(option=option, url=url, verdict="ERROR", detail="", status=fetched.status, seconds=round(fetched.seconds, 2))
    if fetched.off_domain_hosts:
        base.detail = f"redirected outside *.{ALLOWED_DOMAIN} via {', '.join(fetched.off_domain_hosts)}; refused"
        return base
    if fetched.error and fetched.status is None:
        base.detail = fetched.error
        return base
    if fetched.status in _BLOCK_STATUSES:
        base.verdict, base.detail = "BLOCKED", f"HTTP {fetched.status}"
        return base
    if fetched.status is None or fetched.status >= 400:
        base.detail = fetched.error or f"HTTP {fetched.status}"
        return base

    html = fetched.body.decode("utf-8", errors="replace")
    lowered = html[:4000].lower()
    entries = parse_html_page(fetched.body, url, "(untitled)")
    text = "\n".join(e.description for e in entries)
    base.text_chars = len(text)
    base.chunks = len(entries)
    base.links = len(_LINK_RE.findall(html))
    base.dated_items = len(_DATE_RE.findall(text))
    base.scripts = len(_SCRIPT_RE.findall(html))
    base.title = entries[0].title if entries else ""
    base.injection_pattern = _scan_for_injection(text)
    if link_limit:
        base.listing_links = listing_candidates(extract_links(html, url), link_limit)

    if base.text_chars < _MIN_USABLE_CHARS and any(m in lowered for m in _CHALLENGE_MARKERS):
        base.verdict, base.detail = "BLOCKED", "200 OK but the body is a bot-challenge page"
    elif base.text_chars < _MIN_USABLE_CHARS:
        base.verdict = "THIN"
        base.detail = f"{base.text_chars} chars of text, {base.scripts} script tags: likely JavaScript-rendered or a block page"
    else:
        base.verdict = "USABLE"
        base.detail = f"{base.chunks} chunks, {base.text_chars} chars, {base.links} links, {base.dated_items} dated items"
    return base


def build_options(include_paid: bool, env: dict[str, str]) -> list[tuple[str, Optional[Callable[[str, httpx.Client], Fetched]], str]]:
    """(name, fetcher or None, skip reason). A None fetcher is reported as SKIPPED."""
    options: list[tuple[str, Optional[Callable[[str, httpx.Client], Fetched]], str]] = [("httpx", fetch_httpx, "")]
    exa_key = env.get("EXA_API_KEY", "")
    bd_key, bd_zone = env.get("BRIGHTDATA_API_KEY", ""), env.get("BRIGHTDATA_ZONE", "")
    if not include_paid:
        reason = "paid option; pass --include-paid to run"
        options += [("exa", None, reason), ("brightdata", None, reason)]
        return options
    if exa_key:
        options.append(("exa", lambda u, c: fetch_exa(u, c, exa_key), ""))
    else:
        options.append(("exa", None, "EXA_API_KEY not set"))
    if bd_key and bd_zone:
        options.append(("brightdata", lambda u, c: fetch_brightdata(u, c, bd_key, bd_zone), ""))
    else:
        options.append(("brightdata", None, "BRIGHTDATA_API_KEY / BRIGHTDATA_ZONE not set"))
    return options


def run_probe(
    urls: list[str], include_paid: bool, env: dict[str, str], client: httpx.Client, link_limit: int = 0
) -> list[Result]:
    results: list[Result] = []
    for url in urls:
        for name, fetcher, skip_reason in build_options(include_paid, env):
            if fetcher is None:
                results.append(Result(option=name, url=url, verdict="SKIPPED", detail=skip_reason))
                continue
            results.append(analyse(name, url, fetcher(url, client), link_limit))
    return results


def resolve_urls(sources: list[str], urls: list[str]) -> list[str]:
    resolved = [SOURCES_BY_NAME[name].url for name in sources if name in SOURCES_BY_NAME]
    unknown = [name for name in sources if name not in SOURCES_BY_NAME]
    if unknown:
        raise ValueError(f"unknown source name(s): {', '.join(unknown)}")
    return [validate_target(u) for u in [*resolved, *urls]]


def render(results: list[Result]) -> str:
    lines = ["| option | verdict | status | secs | chunks | links | dated | url |", "|---|---|---|---|---|---|---|---|"]
    for r in results:
        lines.append(
            f"| {r.option} | {r.verdict} | {r.status or '-'} | {r.seconds} | {r.chunks} | {r.links} | {r.dated_items} | {r.url} |"
        )
    notes = [f"- {r.option} {r.url}: {r.detail}" for r in results if r.detail]
    flagged = [f"- {r.option} {r.url}: matched injection pattern {r.injection_pattern!r}" for r in results if r.injection_pattern]
    listings: list[str] = []
    for r in results:
        if r.listing_links:
            listings += ["", f"Listing candidates on {r.url} ({r.option}):"]
            listings += [f"- {link['text'] or '(no text)'} -> {link['url']}" for link in r.listing_links]
    return "\n".join(lines + ["", *notes, *(["", "Injection scan hits:", *flagged] if flagged else []), *listings])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", action="append", default=[], help="registered source name (repeatable)")
    parser.add_argument("--url", action="append", default=[], help="extra https URL under *.gov.my (repeatable)")
    parser.add_argument(
        "--links", type=int, default=0, metavar="N", help="also list up to N links per page that look like listings of new material"
    )
    parser.add_argument("--include-paid", action="store_true", help="also run the paid options that have keys set")
    parser.add_argument("--json-out", type=Path, help="write the full results as JSON")
    args = parser.parse_args()

    sources = args.source or ([] if args.url else list(DEFAULT_SOURCES))
    urls = resolve_urls(sources, args.url)
    with httpx.Client(timeout=_TIMEOUT) as client:
        results = run_probe(urls, args.include_paid, dict(os.environ), client, args.links)

    print(render(results))
    if args.json_out:
        args.json_out.write_text(json.dumps([asdict(r) for r in results], indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":  # CLI script: print is the interface here
    sys.exit(main())
