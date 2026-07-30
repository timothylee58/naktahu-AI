"""
Ingest an RSS/Atom feed or a plain HTML page into document_chunks — the table
rag_node's hybrid_search actually queries (distinct from dosm_documents, which
scripts/ingest.py feeds via a separate CSV pipeline).

Intended for periodic sources like Parliament Hansard or a ministry's
announcement feed: run on a schedule (Railway cron, same pattern as
scripts/agents/deadline_monitor.py) and it only embeds/inserts entries
whose content hash isn't already in the table, so re-running the same
feed URL is a cheap no-op for anything already ingested.

Usage:
    python -m scripts.ingest_feed --feed-url https://example.gov.my/hansard/rss \
        --domain government --ministry "Parliament of Malaysia" --language bm

    python -m scripts.ingest_feed --feed-url ... --domain government \
        --ministry "..." --dry-run

Some government portals (notably the MIDA InvestMalaysia sites) publish no
feed at all — they are HTML pages. `--kind html` runs the same dedup,
injection-scan, embed and insert path over text extracted from the page,
chunked so each row is a usable RAG chunk rather than one giant blob:

    python -m scripts.ingest_feed --kind html \
        --feed-url https://www.investmalaysia.gov.my \
        --domain business --ministry "Malaysian Investment Development Authority (MIDA)" \
        --language en --dry-run

Registered sources (scripts/sources.py) can be selected by name instead of
repeating the metadata; --source fills in url/kind/domain/ministry/language:

    python -m scripts.ingest_feed --source invest-malaysia-gov --dry-run
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Optional

import httpx
import structlog
from dotenv import load_dotenv
from supabase import create_client

# apps/api root — works in Docker (/app) and local dev.
_API_ROOT = Path(__file__).resolve().parents[1]
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

from app.agents.rag_node import _embed  # noqa: E402 — reuse the live ILMU→OpenAI embedding fallback
from app.middleware.sanitise import INJECTION_PATTERNS, _fold_confusables  # noqa: E402
from core.config import settings  # noqa: E402
from scripts.sources import SOURCES_BY_NAME, get_source  # noqa: E402

load_dotenv()

log = structlog.get_logger(__name__)

_VALID_DOMAINS = {
    "government", "education", "legal", "finance", "healthcare",
    "epf", "tax", "business", "immigration", "culture", "parliament",
}

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")

# HTML page extraction. There is no pre-existing chunk-size convention in the
# repo (scripts/ingest.py embeds whole CSV rows), so these are declared here as
# the one place to tune them.
_CHUNK_MAX_CHARS = 1200   # roughly 250-350 tokens — a usable hybrid-search unit
_MIN_BLOCK_CHARS = 40     # generic boilerplate filter: nav/footer links are short
_MIN_CHUNK_CHARS = 80     # don't emit a chunk too small to answer anything

# Block-level tags whose boundaries become paragraph breaks during extraction.
_BLOCK_TAGS = frozenset({
    "p", "div", "br", "li", "tr", "td", "th", "section", "article", "header",
    "footer", "nav", "main", "aside", "h1", "h2", "h3", "h4", "h5", "h6",
    "table", "ul", "ol", "blockquote", "pre", "form", "option",
})

_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_HEADING_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.IGNORECASE | re.DOTALL)


@dataclass
class FeedEntry:
    title: str
    description: str
    link: str

    @property
    def content(self) -> str:
        return f"{self.title}\n\n{self.description}".strip()


class _HTMLStripper(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.reset()
        self.convert_charrefs = True
        self.text: list[str] = []
        self.ignore = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        if tag in ("script", "style"):
            self.ignore = True

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style"):
            self.ignore = False

    def handle_data(self, d: str) -> None:
        if not self.ignore:
            self.text.append(d)

    def get_data(self) -> str:
        return "".join(self.text)


def _strip_html(text: str) -> str:
    stripper = _HTMLStripper()
    stripper.feed(text)
    return _WHITESPACE_RE.sub(" ", stripper.get_data()).strip()


class _HTMLBlockStripper(_HTMLStripper):
    """_HTMLStripper (which already drops <script>/<style>) plus paragraph
    breaks at block-level tag boundaries, so a page can be split into text
    blocks instead of collapsing into one unbroken line."""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        super().handle_starttag(tag, attrs)
        if tag in _BLOCK_TAGS:
            self.text.append("\n")

    def handle_endtag(self, tag: str) -> None:
        super().handle_endtag(tag)
        if tag in _BLOCK_TAGS:
            self.text.append("\n")


def extract_blocks(html: str) -> list[str]:
    """Extract visible text blocks from an HTML page.

    Deliberately generic: no site-specific CSS selectors, because the two MIDA
    portals this was written for are unreachable from CI/sandbox (proxy 403),
    so any selector would be an unverifiable guess. Nav/footer boilerplate is
    filtered only by the length heuristic (_MIN_BLOCK_CHARS), which will keep
    some menu text and drop some genuinely short content."""
    stripper = _HTMLBlockStripper()
    stripper.feed(html)
    blocks: list[str] = []
    for raw in stripper.get_data().split("\n"):
        block = _WHITESPACE_RE.sub(" ", raw).strip()
        if len(block) >= _MIN_BLOCK_CHARS:
            blocks.append(block)
    return blocks


def _chunk_blocks(blocks: list[str]) -> list[str]:
    """Pack text blocks into chunks of at most _CHUNK_MAX_CHARS, never splitting
    a block across chunks unless the block alone exceeds the limit."""
    chunks: list[str] = []
    current: list[str] = []
    size = 0
    for block in blocks:
        while len(block) > _CHUNK_MAX_CHARS:
            if current:
                chunks.append("\n\n".join(current))
                current, size = [], 0
            chunks.append(block[:_CHUNK_MAX_CHARS])
            block = block[_CHUNK_MAX_CHARS:]
        if size and size + len(block) + 2 > _CHUNK_MAX_CHARS:
            chunks.append("\n\n".join(current))
            current, size = [], 0
        current.append(block)
        size += len(block) + 2
    if current:
        chunks.append("\n\n".join(current))
    return [c for c in chunks if len(c) >= _MIN_CHUNK_CHARS]


def extract_page_title(html: str, fallback: str) -> str:
    """<title>, else the first <h1>, else the registry/source name."""
    for pattern in (_TITLE_RE, _HEADING_RE):
        match = pattern.search(html)
        if match:
            title = _strip_html(match.group(1))
            if title:
                return title
    return fallback


def parse_html_page(html_bytes: bytes, page_url: str, fallback_title: str) -> list[FeedEntry]:
    """Turn one HTML page into FeedEntry chunks so the HTML path can reuse the
    RSS path's injection scan, content_hash dedup, embedding and insert logic
    unchanged. Every chunk carries the page title and the page URL."""
    html = html_bytes.decode("utf-8", errors="replace")
    title = extract_page_title(html, fallback_title)
    return [
        FeedEntry(title=title, description=chunk, link=page_url)
        for chunk in _chunk_blocks(extract_blocks(html))
    ]


def _scan_for_injection(content: str) -> Optional[str]:
    """Same pattern list applied to user queries and CSV ingestion — a
    poisoned feed entry can't smuggle an indirect prompt injection into
    document_chunks any more than a poisoned CSV row can (scripts/ingest.py).
    Confusables are folded first so Cyrillic/Greek lookalikes can't evade
    the regex patterns, matching the query sanitisation middleware."""
    text = _fold_confusables(unicodedata.normalize("NFKC", content))
    for pattern in INJECTION_PATTERNS:
        if pattern.search(text):
            return pattern.pattern
    return None


def _text(el: Optional[ET.Element]) -> str:
    return (el.text or "").strip() if el is not None else ""


def parse_feed(xml_bytes: bytes) -> list[FeedEntry]:
    """Parse RSS 2.0 <item> or Atom <entry> elements. Namespace-agnostic —
    strips the {namespace} prefix ElementTree leaves on tag names so this
    doesn't need to know each feed's exact namespace declarations."""
    root = ET.fromstring(xml_bytes)
    entries: list[FeedEntry] = []

    for el in root.iter():
        tag = el.tag.rsplit("}", 1)[-1]
        if tag not in ("item", "entry"):
            continue

        children: dict[str, ET.Element] = {}
        links: list[ET.Element] = []
        for child in el:
            tag_name = child.tag.rsplit("}", 1)[-1]
            if tag_name == "link":
                links.append(child)
            else:
                children[tag_name] = child

        title = _text(children.get("title"))
        description = (
            _text(children.get("encoded"))
            or _text(children.get("description"))
            or _text(children.get("summary"))
            or _text(children.get("content"))
        )

        link = ""
        for link_el in links:
            href = link_el.get("href")
            if href:
                rel = link_el.get("rel")
                if not rel or rel == "alternate":
                    link = href
                    break
            else:
                val = _text(link_el)
                if val:
                    link = val
        if not link and links:
            link = links[0].get("href") or _text(links[0])

        if not title:
            continue
        entries.append(FeedEntry(title=title, description=_strip_html(description), link=link))

    return entries


def fetch_feed(url: str) -> bytes:
    with httpx.Client(timeout=20.0, follow_redirects=True) as client:
        resp = client.get(url, headers={"User-Agent": "NakTahu-FeedIngest/1.0"})
        resp.raise_for_status()
        return resp.content


def _existing_hashes(supabase, hashes: list[str]) -> set[str]:
    if not hashes:
        return set()
    res = supabase.table("document_chunks").select("content_hash").in_("content_hash", hashes).execute()
    return {row["content_hash"] for row in (res.data or [])}


async def main_async(args: argparse.Namespace) -> None:
    supabase = None if args.dry_run else create_client(settings.supabase_url, settings.supabase_service_key)

    # getattr default keeps callers that predate --kind (and existing tests)
    # on the RSS path unchanged.
    kind = getattr(args, "kind", "rss")
    is_html = kind == "html"

    print(f"Fetching {'page' if is_html else 'feed'}: {args.feed_url}")
    try:
        raw_bytes = fetch_feed(args.feed_url)
    except httpx.HTTPError as exc:
        print(f"ERROR: failed to fetch {'page' if is_html else 'feed'} — {exc}", file=sys.stderr)
        sys.exit(1)

    if is_html:
        fallback_title = getattr(args, "source_title", None) or args.feed_url
        entries = parse_html_page(raw_bytes, args.feed_url, fallback_title)[: args.limit]
    else:
        try:
            entries = parse_feed(raw_bytes)[: args.limit]
        except ET.ParseError as exc:
            print(f"ERROR: failed to parse XML feed — {exc}", file=sys.stderr)
            sys.exit(1)
    print(f"Parsed {len(entries)} entries (limit {args.limit})")

    skipped_injection = 0
    candidates: list[tuple[FeedEntry, str]] = []
    for entry in entries:
        matched = _scan_for_injection(entry.content)
        if matched:
            skipped_injection += 1
            log.warning(
                "feed_entry_skipped_injection_suspected",
                feed_url=args.feed_url,
                title=entry.title[:80],
                matched_pattern=matched,
                dry_run=args.dry_run,
            )
            continue
        content_hash = hashlib.sha256(entry.content.encode()).hexdigest()
        candidates.append((entry, content_hash))

    if skipped_injection:
        print(f"Skipped {skipped_injection} entr(ies) — prompt-injection pattern suspected (see warnings above).")

    if not candidates:
        print("Nothing to ingest.")
        return

    already = set() if args.dry_run else _existing_hashes(supabase, [h for _, h in candidates])
    new_entries = [(e, h) for e, h in candidates if h not in already]
    print(f"{len(new_entries)} new entr(ies) to embed and insert ({len(candidates) - len(new_entries)} already ingested)")

    inserted = 0
    errors = 0
    for entry, content_hash in new_entries:
        try:
            embedding = await _embed(entry.content)
        except Exception as exc:
            print(f"  FAILED (embedding) — {entry.title[:60]!r}: {exc}")
            errors += 1
            continue

        if args.dry_run:
            print(f"  OK (dry-run) — {entry.title[:60]!r}")
            continue

        row = {
            "content": entry.content,
            "content_hash": content_hash,
            "language": args.language,
            "domain": args.domain,
            "source_title": entry.title,
            "source_url": entry.link or args.feed_url,
            "ministry": args.ministry,
            "embedding": embedding,
        }
        try:
            supabase.table("document_chunks").insert(row).execute()
            inserted += 1
            print(f"  OK — {entry.title[:60]!r}")
        except Exception as exc:
            print(f"  FAILED (insert) — {entry.title[:60]!r}: {exc}")
            errors += 1

    print(f"\n{'='*60}")
    if args.dry_run:
        print(f"Dry-run complete — {len(new_entries)} entr(ies) would be inserted, no data written.")
    else:
        print(f"Ingestion complete: {inserted} inserted, {errors} errors.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest an RSS/Atom feed or an HTML page into document_chunks"
    )
    parser.add_argument(
        "--source",
        choices=sorted(SOURCES_BY_NAME),
        help="Registered source from scripts/sources.py — fills in url/kind/domain/ministry/language",
    )
    parser.add_argument("--feed-url", help="RSS/Atom feed URL, or page URL with --kind html")
    parser.add_argument("--kind", default="rss", choices=["rss", "html"], help="Source type (default: rss)")
    parser.add_argument("--domain", choices=sorted(_VALID_DOMAINS))
    parser.add_argument("--ministry", help="Attributed source, e.g. 'Parliament of Malaysia'")
    parser.add_argument("--language", default="bm", choices=["bm", "en", "zh"])
    parser.add_argument("--limit", type=int, default=50, help="Max entries/chunks per run")
    parser.add_argument("--dry-run", action="store_true", help="Parse and embed but do not write to Supabase")
    parser.add_argument("--source-title", help="Fallback title for HTML pages with no <title>/<h1>")
    args = parser.parse_args()

    if args.source:
        source = get_source(args.source)
        args.feed_url = args.feed_url or source.url
        args.kind = source.kind
        args.domain = args.domain or source.domain
        args.ministry = args.ministry or source.ministry
        args.language = source.language if args.language == "bm" else args.language
        args.source_title = args.source_title or source.name

    missing = [n for n in ("feed_url", "domain", "ministry") if not getattr(args, n)]
    if missing:
        parser.error(
            "missing required argument(s): "
            + ", ".join("--" + n.replace("_", "-") for n in missing)
            + " (or pass --source)"
        )

    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
