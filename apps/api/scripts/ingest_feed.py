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

Official documents published only as PDFs (the Budget speech, Fiscal
Outlook) use `--kind pdf`: text is extracted per page with pypdf, chunked the
same way as HTML, and every chunk cites the PDF's own URL with `#page=N`. A
document that spans several subjects can tag each chunk with its own domain
(`--route-domains`, see route_domain) instead of one domain for the whole run:

    python -m scripts.ingest_feed --kind pdf --route-domains \
        --feed-url https://belanjawan.mof.gov.my/pdf/belanjawan2026/ucapan/bs26.pdf \
        --domain finance --ministry "Kementerian Kewangan Malaysia (MOF)" \
        --language en --dry-run

A registered source with `available_from` in the future (Budget 2027 before
it's tabled) exits cleanly with an UPCOMING notice instead of fetching.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import io
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date
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

# Reuses the query path's embedder on purpose: rows written here are searched
# by rag_node, so both sides must use the same model or the stored vectors and
# the query vector end up in different spaces. _embed only ever routes between
# two providers of the SAME model (ILMU gateway, then OpenAI direct) and raises
# if neither works — a failed embed skips the row, never writes an incompatible
# vector into document_chunks. See llm_client.py's embeddings section.
from app.agents.analyst_node import _STRICT_DOMAINS  # noqa: E402
from app.agents.rag_node import _embed  # noqa: E402
from app.middleware.sanitise import INJECTION_PATTERNS, _fold_confusables  # noqa: E402
from core.config import settings  # noqa: E402
from scripts.effective_dates import extract_validity_window, parse_published  # noqa: E402
from scripts.sources import SOURCES_BY_NAME, get_source  # noqa: E402

load_dotenv()

log = structlog.get_logger(__name__)

_VALID_DOMAINS = {
    "government", "education", "legal", "finance", "healthcare",
    "epf", "tax", "business", "immigration", "culture", "parliament", "property",
    "welfare", "scam_check",
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
    # Per-chunk domain from route_domain; None means "use the run's --domain".
    domain: Optional[str] = None
    # Feed item's publish date (RSS pubDate / Atom published). Stored as
    # announced_date: for a ministry announcement it is when the change was
    # announced. None for HTML/PDF sources, which carry no per-item date.
    published: Optional[date] = None

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


def parse_pdf(pdf_bytes: bytes, pdf_url: str, fallback_title: str) -> list[FeedEntry]:
    """Turn a PDF into page-anchored FeedEntry chunks, so the PDF path goes
    through the same injection scan, dedup, embed and insert as RSS/HTML.

    Chunks never span pages: each one cites `<pdf_url>#page=N`, which browsers
    open at that page — a citation chip lands on the actual paragraph rather
    than page 1 of a 60-page speech. Paragraphs are split on blank lines; pypdf
    often emits none, so single lines are the fallback unit and _chunk_blocks
    packs them back up to _CHUNK_MAX_CHARS."""
    from pypdf import PdfReader  # type: ignore[import-untyped]

    reader = PdfReader(io.BytesIO(pdf_bytes))
    meta_title = ""
    try:
        meta_title = ((reader.metadata or {}).get("/Title") or "").strip()
    except Exception:  # malformed metadata must not block the text
        meta_title = ""
    title = meta_title or fallback_title

    entries: list[FeedEntry] = []
    for page_no, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception as exc:
            log.warning("pdf_page_extract_failed", url=pdf_url, page=page_no, error=str(exc))
            continue
        paragraphs = re.split(r"\n\s*\n", text)
        if len(paragraphs) == 1:
            paragraphs = text.split("\n")
        blocks = [b for b in (_WHITESPACE_RE.sub(" ", p).strip() for p in paragraphs) if b]
        for chunk in _chunk_blocks(blocks):
            entries.append(FeedEntry(
                title=f"{title} (p. {page_no})",
                description=chunk,
                link=f"{pdf_url}#page={page_no}",
            ))
    return entries


# Per-chunk domain routing for multi-subject documents (the Budget speech
# covers tax, cash aid, schools, hospitals, EPF and housing in one PDF).
# Deliberately a deterministic keyword score, not an LLM call: it's
# reproducible, testable, free, and a wrong guess only costs a chunk being
# filed under a neighbouring domain — hybrid search still finds it by text.
# Keywords are BM + EN, lowercase, matched on word boundaries.
_DOMAIN_KEYWORDS: dict[str, tuple[str, ...]] = {
    "tax": (
        "cukai", "tax", "taxes", "sst", "income tax", "cukai pendapatan", "duti setem",
        "stamp duty", "rpgt", "excise", "eksais", "pelepasan cukai", "tax relief",
        "tax incentive", "insentif cukai", "lhdn", "withholding", "e-invois", "e-invoice",
        "tax deduction", "potongan cukai",
    ),
    "welfare": (
        "str", "sumbangan tunai rahmah", "sara", "sumbangan asas rahmah", "bantuan",
        "b40", "golongan rentan", "vulnerable", "cash aid", "welfare", "kebajikan",
        "jkm", "oku", "warga emas", "senior citizens", "persons with disabilities",
        "subsidi", "subsidy", "subsidies", "social protection", "perlindungan sosial",
    ),
    "business": (
        "pks", "msme", "msmes", "sme", "smes", "usahawan", "entrepreneur",
        "entrepreneurs", "perniagaan", "business", "businesses", "pembiayaan",
        "financing", "geran", "grant", "grants", "startup", "startups", "tekun",
        "sme corp", "mida", "pelaburan", "investment", "nimp", "industri", "industry",
        "eksport", "export",
    ),
    "education": (
        "pendidikan", "education", "sekolah", "school", "schools", "pelajar",
        "student", "students", "universiti", "university", "universities", "ptptn",
        "tvet", "guru", "teacher", "teachers", "biasiswa", "scholarship",
        "scholarships", "kpm", "kpt",
    ),
    "healthcare": (
        "kesihatan", "health", "healthcare", "hospital", "hospitals", "klinik",
        "clinic", "clinics", "perubatan", "medical", "kkm", "moh", "doktor",
        "doctors", "jururawat", "nurses", "ubat", "medicine", "mental health",
    ),
    "epf": (
        "kwsp", "epf", "i-saraan", "caruman", "contribution", "contributions",
        "persaraan", "retirement", "akaun fleksibel", "flexible account", "perkeso",
        "socso",
    ),
    "property": (
        "rumah", "perumahan", "housing", "home", "homes", "rumah mampu milik",
        "affordable housing", "pr1ma", "rent-to-own", "sewa", "rental", "hartanah",
        "property", "properties", "pembeli rumah pertama", "first-time homebuyers",
        "skim jaminan kredit perumahan",
    ),
}
_DOMAIN_PATTERNS: dict[str, re.Pattern[str]] = {
    domain: re.compile(r"\b(?:" + "|".join(re.escape(k) for k in kws) + r")\b", re.IGNORECASE)
    for domain, kws in _DOMAIN_KEYWORDS.items()
}
_ROUTE_MIN_HITS = 2  # one incidental "cukai" in a chunk about schools isn't a tax chunk


def route_domain(text: str, fallback: str) -> str:
    """The domain whose keywords hit `text` most often (at least
    _ROUTE_MIN_HITS times), else `fallback`. Ties go to the earlier domain in
    _DOMAIN_KEYWORDS, so the result is deterministic."""
    best, best_hits = fallback, _ROUTE_MIN_HITS - 1
    for domain, pattern in _DOMAIN_PATTERNS.items():
        hits = len(pattern.findall(text))
        if hits > best_hits:
            best, best_hits = domain, hits
    return best


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
        published = parse_published(
            _text(children.get("pubDate")) or _text(children.get("published")) or _text(children.get("updated"))
        )
        entries.append(FeedEntry(title=title, description=_strip_html(description), link=link, published=published))

    return entries


def fetch_feed(url: str) -> bytes:
    with httpx.Client(timeout=20.0, follow_redirects=True) as client:
        resp = client.get(url, headers={"User-Agent": "NakTahu-FeedIngest/1.0"})
        resp.raise_for_status()
        return resp.content


# PostgREST sends .in_() as a GET query string; each sha256 hash adds ~65
# chars, so a long PDF's hundreds of chunks would overflow the server's
# URI limit in one request. 100 hashes keeps each URL around 7KB.
_HASH_BATCH = 100


def _existing_hashes(supabase, hashes: list[str]) -> set[str]:
    found: set[str] = set()
    for i in range(0, len(hashes), _HASH_BATCH):
        res = supabase.table("document_chunks").select("content_hash").in_("content_hash", hashes[i : i + _HASH_BATCH]).execute()
        found.update(row["content_hash"] for row in (res.data or []))
    return found


# Pre-052 databases have no effective_until/announced_date columns; an insert
# naming them fails. Matched against the error text to retry without them.
_DATE_COLUMNS = ("effective_date", "effective_until", "announced_date")

# Supersede candidates: how similar (hybrid_search's combined 0.7 cosine +
# 0.3 keyword score) an older chunk must be to be queued for review, and how
# many neighbours to look at. Tunable; a false candidate only costs a reviewer
# a "reject", while auto-retiring is never done (see migration 053).
_SUPERSEDE_MIN_SIMILARITY = 0.75
_SUPERSEDE_NEIGHBOURS = 5


def _date_arg(args: argparse.Namespace, name: str) -> Optional[date]:
    """An ISO date CLI override, or None. Tolerates mock namespaces in tests."""
    value = getattr(args, name, None)
    if not isinstance(value, str) or not value:
        return None
    return date.fromisoformat(value)


def date_fields(entry: FeedEntry, args: argparse.Namespace) -> dict[str, str]:
    """effective_date / effective_until / announced_date for one row.

    CLI overrides win (for a document whose dates a human has checked, e.g.
    a Budget PDF); otherwise the text is scanned for explicit validity phrases
    (scripts/effective_dates.py). Only known dates are returned, so a row with
    none keeps today's behaviour and pre-052 databases see no new columns.
    """
    window = extract_validity_window(entry.content)
    values = {
        "effective_date": _date_arg(args, "effective_date") or window.effective_date,
        "effective_until": _date_arg(args, "effective_until") or window.effective_until,
        "announced_date": _date_arg(args, "announced_date") or entry.published,
    }
    return {k: v.isoformat() for k, v in values.items() if v is not None}


def _insert_chunk(supabase, row: dict) -> Optional[str]:
    """Insert one row and return its id; retry without date columns pre-052."""
    try:
        res = supabase.table("document_chunks").insert(row).execute()
    except Exception as exc:
        dated = [k for k in _DATE_COLUMNS if k in row]
        if not dated or not any(k in str(exc) for k in _DATE_COLUMNS):
            raise
        log.warning("ingest_date_columns_unsupported", columns=dated, error=str(exc)[:200])
        res = supabase.table("document_chunks").insert({k: v for k, v in row.items() if k not in dated}).execute()
    data = res.data if isinstance(res.data, list) else []
    return data[0].get("id") if data else None


def queue_supersede_candidates(
    supabase, new_id: str, title: str, embedding: list[float], domain: str, effective_date: Optional[str]
) -> int:
    """Queue older, very similar chunks in the same domain for human review.

    Only for time-sensitive domains, and only when the new chunk states when
    it takes effect — that is what makes it a new version of a rule rather
    than a re-published page. Never marks anything superseded itself.
    Best-effort: a failure here (e.g. migration 053 not applied) is logged and
    never fails the ingestion run.
    """
    if domain not in _STRICT_DOMAINS or not effective_date or not new_id:
        return 0
    try:
        res = supabase.rpc("hybrid_search", {
            "query_text": title,
            "query_embedding": embedding,
            "domain_filter": domain,
            "match_count": _SUPERSEDE_NEIGHBOURS,
        }).execute()
        neighbours = res.data if isinstance(res.data, list) else []
        rows = [
            {"new_chunk_id": new_id, "old_chunk_id": n["id"], "similarity": float(n["similarity"])}
            for n in neighbours
            if n.get("id") != new_id
            and float(n.get("similarity") or 0) >= _SUPERSEDE_MIN_SIMILARITY
            and (not n.get("effective_date") or str(n["effective_date"]) < effective_date)
        ]
        if rows:
            supabase.table("supersede_candidates").upsert(
                rows, on_conflict="new_chunk_id,old_chunk_id", ignore_duplicates=True
            ).execute()
        return len(rows)
    except Exception as exc:
        log.warning("supersede_candidates_failed", new_chunk_id=new_id, error=str(exc)[:200])
        return 0


async def main_async(args: argparse.Namespace) -> None:
    # Real Supabase client regardless of dry_run — dry-run's contract is "no
    # WRITES", not "no reads". Before this fix, dry-run hardcoded `already =
    # set()` below, which meant the weekly scheduled dry-run cron
    # (ingest-sources.yml) re-embedded every entry from every source on
    # EVERY run forever, even entries it had already seen and embedded in
    # every prior week's run — a real, recurring ILMU API cost for zero
    # benefit, since dry-run's whole purpose is "check content looks right",
    # not "burn tokens re-confirming unchanged content every week".
    supabase = create_client(settings.supabase_url, settings.supabase_service_key)

    # getattr default keeps callers that predate --kind (and existing tests)
    # on the RSS path unchanged.
    kind = getattr(args, "kind", "rss")
    is_html = kind == "html"
    noun = {"html": "page", "pdf": "PDF"}.get(kind, "feed")

    print(f"Fetching {noun}: {args.feed_url}")
    try:
        raw_bytes = fetch_feed(args.feed_url)
    except httpx.HTTPError as exc:
        print(f"ERROR: failed to fetch {noun} — {exc}", file=sys.stderr)
        sys.exit(1)

    fallback_title = getattr(args, "source_title", None) or args.feed_url
    if is_html:
        entries = parse_html_page(raw_bytes, args.feed_url, fallback_title)[: args.limit]
    elif kind == "pdf":
        try:
            entries = parse_pdf(raw_bytes, args.feed_url, fallback_title)[: args.limit]
        except Exception as exc:  # pypdf raises several unrelated types on bad input
            print(f"ERROR: failed to parse PDF — {exc}", file=sys.stderr)
            sys.exit(1)
    else:
        try:
            entries = parse_feed(raw_bytes)[: args.limit]
        except ET.ParseError as exc:
            print(f"ERROR: failed to parse XML feed — {exc}", file=sys.stderr)
            sys.exit(1)
    print(f"Parsed {len(entries)} entries (limit {args.limit})")

    # `is True`: callers passing a MagicMock namespace (tests) mustn't opt in by accident.
    if getattr(args, "route_domains", False) is True:
        for entry in entries:
            entry.domain = route_domain(entry.content, args.domain)
        counts: dict[str, int] = {}
        for entry in entries:
            counts[entry.domain or args.domain] = counts.get(entry.domain or args.domain, 0) + 1
        print("Domain routing: " + ", ".join(f"{d}={n}" for d, n in sorted(counts.items())))

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

    # Read-only, runs in both modes now (see the comment on `supabase` above)
    # — this is the actual fix: an entry already embedded in a prior run
    # (dry or live) is skipped here, before the token-costing _embed() call
    # below, instead of every entry being re-embedded on every scheduled
    # dry-run regardless of whether anything changed.
    already = _existing_hashes(supabase, [h for _, h in candidates])
    new_entries = [(e, h) for e, h in candidates if h not in already]
    skipped_unchanged = len(candidates) - len(new_entries)
    print(f"{len(new_entries)} new entr(ies) to embed and insert ({skipped_unchanged} already ingested — skipped, not re-embedded)")

    inserted = 0
    errors = 0
    for entry, content_hash in new_entries:
        try:
            embedding = await _embed(entry.content)
        except Exception as exc:
            print(f"  FAILED (embedding) — {entry.title[:60]!r}: {exc}")
            errors += 1
            continue

        dates = date_fields(entry, args)
        if args.dry_run:
            dated = f" {dates}" if dates else ""
            print(f"  OK (dry-run) [{entry.domain or args.domain}]{dated} — {entry.title[:60]!r}")
            continue

        row = {
            "content": entry.content,
            "content_hash": content_hash,
            "language": args.language,
            "domain": entry.domain or args.domain,
            "source_title": entry.title,
            "source_url": entry.link or args.feed_url,
            "ministry": args.ministry,
            "embedding": embedding,
            **dates,
        }
        try:
            new_id = _insert_chunk(supabase, row)
            inserted += 1
            print(f"  OK — {entry.title[:60]!r}")
            queued = queue_supersede_candidates(
                supabase, new_id, entry.title, embedding, row["domain"], dates.get("effective_date")
            )
            if queued:
                print(f"    queued {queued} possible superseded chunk(s) for review (scripts/review_supersede.py)")
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
    parser.add_argument("--kind", default="rss", choices=["rss", "html", "pdf"], help="Source type (default: rss)")
    parser.add_argument("--domain", choices=sorted(_VALID_DOMAINS), help="Domain (the fallback domain with --route-domains)")
    parser.add_argument(
        "--route-domains",
        action="store_true",
        help="Tag each chunk with its own domain by keyword (for multi-subject documents like the Budget speech)",
    )
    parser.add_argument("--ministry", help="Attributed source, e.g. 'Parliament of Malaysia'")
    parser.add_argument("--language", default="bm", choices=["bm", "en", "zh"])
    parser.add_argument("--limit", type=int, default=50, help="Max entries/chunks per run")
    parser.add_argument("--dry-run", action="store_true", help="Parse and embed but do not write to Supabase")
    parser.add_argument("--source-title", help="Fallback title for HTML pages with no <title>/<h1>")
    parser.add_argument("--effective-date", help="YYYY-MM-DD the rule takes effect (overrides text extraction)")
    parser.add_argument("--effective-until", help="YYYY-MM-DD last day the rule applies (overrides text extraction)")
    parser.add_argument("--announced-date", help="YYYY-MM-DD the change was announced (overrides the feed date)")
    args = parser.parse_args()

    if args.source:
        source = get_source(args.source)
        if not source.is_available():
            assert source.available_from is not None
            days = (source.available_from - date.today()).days
            print(
                f"UPCOMING — {source.name} is published from {source.available_from.isoformat()} "
                f"({days} day(s) away); nothing fetched."
            )
            return
        args.route_domains = args.route_domains or source.route_domains
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
