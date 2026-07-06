"""
Ingest an RSS/Atom feed into document_chunks — the table rag_node's
hybrid_search actually queries (distinct from dosm_documents, which
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
from app.middleware.sanitise import INJECTION_PATTERNS  # noqa: E402
from core.config import settings  # noqa: E402

load_dotenv()

log = structlog.get_logger(__name__)

_VALID_DOMAINS = {
    "government", "education", "legal", "finance", "healthcare",
    "epf", "tax", "business", "immigration", "culture",
}

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


@dataclass
class FeedEntry:
    title: str
    description: str
    link: str

    @property
    def content(self) -> str:
        return f"{self.title}\n\n{self.description}".strip()


def _strip_html(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", _HTML_TAG_RE.sub(" ", text)).strip()


def _scan_for_injection(content: str) -> Optional[str]:
    """Same pattern list applied to user queries and CSV ingestion — a
    poisoned feed entry can't smuggle an indirect prompt injection into
    document_chunks any more than a poisoned CSV row can (scripts/ingest.py)."""
    text = unicodedata.normalize("NFKC", content)
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

        children = {child.tag.rsplit("}", 1)[-1]: child for child in el}
        title = _text(children.get("title"))
        description = _text(children.get("description")) or _text(children.get("summary")) or _text(children.get("content"))
        link_el = children.get("link")
        if link_el is not None:
            link = link_el.get("href") or _text(link_el)
        else:
            link = ""

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

    print(f"Fetching feed: {args.feed_url}")
    try:
        xml_bytes = fetch_feed(args.feed_url)
    except httpx.HTTPError as exc:
        print(f"ERROR: failed to fetch feed — {exc}", file=sys.stderr)
        sys.exit(1)

    entries = parse_feed(xml_bytes)[: args.limit]
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
    parser = argparse.ArgumentParser(description="Ingest an RSS/Atom feed into document_chunks")
    parser.add_argument("--feed-url", required=True, help="RSS or Atom feed URL")
    parser.add_argument("--domain", required=True, choices=sorted(_VALID_DOMAINS))
    parser.add_argument("--ministry", required=True, help="Attributed source, e.g. 'Parliament of Malaysia'")
    parser.add_argument("--language", default="bm", choices=["bm", "en", "zh"])
    parser.add_argument("--limit", type=int, default=50, help="Max entries per run")
    parser.add_argument("--dry-run", action="store_true", help="Parse and embed but do not write to Supabase")
    args = parser.parse_args()

    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
