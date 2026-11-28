#!/usr/bin/env python3
"""Policy watcher: notice new items on ministry and state listing pages and put
them in a human review queue (policy_watch_items, migration 063).

What it does NOT do: write to document_chunks, call an embedding API, or touch
anything a live answer reads. Approved items are not ingested here; that is a
separate, later step. Free fetching only (plain httpx).

Usage (from apps/api):

    python -m scripts.policy_watch scan --dry-run                 # print what it finds, write nothing
    python -m scripts.policy_watch scan --target hasil-media      # one target, queue the new items
    python -m scripts.policy_watch list --status pending
    python -m scripts.policy_watch review approve <id> [<id> ...] --note "ok"
    python -m scripts.policy_watch review reject <id> --note "not policy"

Env for anything that writes: SUPABASE_URL and SUPABASE_SERVICE_KEY (or
SUPABASE_SERVICE_ROLE_KEY). Without them `scan` falls back to a dry run.

How a scan decides:
  * The first scan of a target records everything it sees as `baseline`, so the
    existing back catalogue never floods the review queue.
  * After that, a link not seen before is `pending`.
  * If a single scan would queue more than MAX_NEW_PER_TARGET items, nothing is
    queued: that is almost always a redesign that changed every URL, not 50 new
    policies, and the target is reported for a human to look at.
  * Link titles are scanned for prompt injection; flagged ones are skipped.

Until migration 063 is applied the scan prints what it found plus the file to
paste into the Supabase SQL editor, and exits 0 rather than crashing.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence
from urllib.parse import quote, unquote, urldefrag, urljoin, urlsplit

import httpx

_API_ROOT = Path(__file__).resolve().parents[1]
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

from scripts.ingest_feed import _host_in_domain, _scan_for_injection, fetch_feed  # noqa: E402
from scripts.watch_targets import TARGETS, TARGETS_BY_NAME, WatchTarget  # noqa: E402

TABLE = "policy_watch_items"
MIGRATION_FILE = "infra/supabase/migrations/063_policy_watch_items.sql"
MAX_NEW_PER_TARGET = 50
_MAX_TITLE = 500
_PAGE_SIZE = 1000
_SKIP_EXTENSIONS = (".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".ico", ".css", ".js", ".zip", ".mp4", ".mp3")
_TABLE_MISSING_CODES = frozenset({"PGRST205", "42P01"})

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "mac": 3, "apr": 4, "may": 5, "mei": 5, "jun": 6, "jul": 7,
    "aug": 8, "ogo": 8, "sep": 9, "oct": 10, "okt": 10, "nov": 11, "dec": 12, "dis": 12,
}
_NAMED_DATE_RE = re.compile(r"\b(\d{1,2})\s+([A-Za-z]{3,9})\.?\s+(\d{4})\b")
_NUMERIC_DATE_RE = re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b")
_ISO_DATE_RE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")


class QueueUnavailable(RuntimeError):
    """The review-queue table does not exist yet (migration 063 not applied)."""


@dataclass(frozen=True)
class Item:
    url: str
    title: str
    published_on: Optional[date] = None


def parse_date(text: str) -> Optional[date]:
    """First plausible date in `text`. Day first, as Malaysian sites write it."""
    for match in _ISO_DATE_RE.finditer(text):
        year, month, day = (int(g) for g in match.groups())
        parsed = _safe_date(year, month, day)
        if parsed:
            return parsed
    for match in _NAMED_DATE_RE.finditer(text):
        month = _MONTHS.get(match.group(2)[:3].lower())
        if month:
            parsed = _safe_date(int(match.group(3)), month, int(match.group(1)))
            if parsed:
                return parsed
    for match in _NUMERIC_DATE_RE.finditer(text):
        parsed = _safe_date(int(match.group(3)), int(match.group(2)), int(match.group(1)))
        if parsed:
            return parsed
    return None


def _safe_date(year: int, month: int, day: int) -> Optional[date]:
    try:
        parsed = date(year, month, day)
    except ValueError:
        return None
    return parsed if 2000 <= parsed.year <= date.today().year + 1 else None


def _strip_trailing_date(title: str) -> str:
    """Titles often end with the date the page prints next to them; keep the words."""
    stripped = _NAMED_DATE_RE.sub(lambda m: "" if _MONTHS.get(m.group(2)[:3].lower()) else m.group(0), title)
    stripped = _NUMERIC_DATE_RE.sub("", stripped)
    return " ".join(stripped.split()) or title


class _AnchorTokens(HTMLParser):
    """Anchors plus the plain text around them, in document order."""

    def __init__(self) -> None:
        super().__init__()
        self.tokens: list[tuple[str, str, str]] = []  # (kind, href, text)
        self._href: Optional[str] = None
        self._text: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        if tag in ("script", "style"):
            self._skip_depth += 1
        elif tag == "a" and self._href is None:
            self._href = dict(attrs).get("href") or ""
            self._text = []

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style") and self._skip_depth:
            self._skip_depth -= 1
        elif tag == "a" and self._href is not None:
            self.tokens.append(("a", self._href, " ".join("".join(self._text).split())))
            self._href = None

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if self._href is not None:
            self._text.append(data)
        elif data.strip():
            self.tokens.append(("t", "", " ".join(data.split())))


_DATE_REACH = 3  # tokens to look past on each side of a link


def _nearby_date(tokens: list[tuple[str, str, str]], index: int, absolute: str, target: WatchTarget) -> Optional[date]:
    """A date printed beside a link, not inside it. Looks up to _DATE_REACH tokens
    either way and steps over other links to the SAME address, because a card
    usually links its image and its title separately with the date next to one
    of them. Any other link ends the search: that date belongs to a different item."""
    for step in (-1, 1):
        for j in range(index + step, index + step * (_DATE_REACH + 1), step):
            if not 0 <= j < len(tokens):
                break
            kind, href, text = tokens[j]
            if kind == "t":
                found = parse_date(text)
                if found:
                    return found
                continue
            if urldefrag(urljoin(target.url, href.strip()))[0] != absolute:
                break
    return None


def _preceding_title(tokens: list[tuple[str, str, str]], index: int, absolute: str, target: WatchTarget) -> str:
    """The headline of a card whose link only says "Read More": the closest plain
    text before the link that is long enough to be a title and is not just a date.
    Links to the same address are stepped over; any other link ends the search."""
    for j in range(index - 1, max(index - 1 - _DATE_REACH, -1), -1):
        kind, href, text = tokens[j]
        if kind == "t":
            candidate = _strip_trailing_date(text)
            if len(candidate) >= target.min_title_chars and not parse_date(candidate):
                return text
            continue
        if urldefrag(urljoin(target.url, href.strip()))[0] != absolute:
            break
    return ""


class _DataAttrAnchors(HTMLParser):
    """Anchors that keep their address in a data-* attribute: (address, data-title, text)."""

    def __init__(self, attr: str) -> None:
        super().__init__()
        self._attr = attr
        self.found: list[tuple[str, str, str]] = []
        self._open: Optional[list[str]] = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        if tag != "a":
            return
        values = dict(attrs)
        address = (values.get(self._attr) or "").strip()
        if address:
            self._open = [address, (values.get("data-title") or "").strip()]
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._open is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._open is not None:
            self.found.append((self._open[0], self._open[1], " ".join("".join(self._text).split())))
            self._open = None


def _title_from_filename(path: str) -> str:
    stem = unquote(urlsplit(path).path.rsplit("/", 1)[-1]).rsplit(".", 1)[0]
    stem = re.sub(r"^\d{6,}_", "", stem)
    return " ".join(stem.replace("_", " ").split())


def _extract_data_attr_items(html: str, target: WatchTarget) -> list[Item]:
    parser = _DataAttrAnchors(target.document_attr)
    parser.feed(html)
    suffix = target.host_suffix
    seen: set[str] = set()
    items: list[Item] = []
    for address, data_title, text in parser.found:
        absolute = urldefrag(urljoin(target.url, address))[0]
        parts = urlsplit(absolute)
        if parts.scheme not in ("http", "https") or not parts.hostname or not _host_in_domain(parts.hostname, suffix):
            continue
        # Spaces in file names are legal on this site but not in a stored URL.
        absolute = quote(absolute, safe=":/%?=&")
        if absolute in seen:
            continue
        title = " ".join((data_title or text or "").split())
        if len(title) < target.min_title_chars:
            title = _title_from_filename(absolute)
        if len(title) < target.min_title_chars:
            continue
        published = parse_date(title)
        if target.require_date and published is None:
            continue
        seen.add(absolute)
        items.append(Item(url=absolute, title=title[:_MAX_TITLE], published_on=published))
    return items


def extract_items(html: str, target: WatchTarget) -> list[Item]:
    if target.document_attr:
        return _extract_data_attr_items(html, target)
    return _extract_link_items(html, target)


def _extract_link_items(html: str, target: WatchTarget) -> list[Item]:
    """Items on a listing page: links that stay on the agency's own host, carry a
    real title, and (when the target says so) live under an item path prefix.
    The date comes from the link text, else the text right after or before it."""
    parser = _AnchorTokens()
    parser.feed(html)
    suffix = target.host_suffix
    listing_url = urldefrag(target.url)[0]
    seen: set[str] = set()
    items: list[Item] = []
    tokens = parser.tokens
    for index, (kind, href, text) in enumerate(tokens):
        if kind != "a" or not href.strip():
            continue
        absolute = urldefrag(urljoin(target.url, href.strip()))[0]
        parts = urlsplit(absolute)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            continue
        if not _host_in_domain(parts.hostname, suffix):
            continue
        if absolute in seen or absolute == listing_url or parts.path.lower().endswith(_SKIP_EXTENSIONS):
            continue
        if target.item_url_prefixes and not absolute.startswith(target.item_url_prefixes):
            continue
        published = parse_date(text) or _nearby_date(tokens, index, absolute, target)
        if target.require_date and published is None:
            continue
        title = _strip_trailing_date(text)
        if target.title_from_preceding_text and len(title) < target.min_title_chars:
            title = _strip_trailing_date(_preceding_title(tokens, index, absolute, target))
        if len(title) < target.min_title_chars:
            continue
        seen.add(absolute)
        items.append(Item(url=absolute, title=title[:_MAX_TITLE], published_on=published))
    return items


def diagnose(html: str, target: WatchTarget, limit: int = 10) -> list[str]:
    """Why a page produced no items: counts at each filter, then the evidence a
    person needs to fix the target. Printed only for a target that came back
    empty, so a layout the extractor does not understand can be read from the log.

    Three views, because navigation menus bury the real list at the top of the
    link order: the first same-host links, links that live under the listing's own
    path (where items usually are), and dates found in plain text with the links
    on either side of them (shows whether a date sits next to its link at all)."""
    parser = _AnchorTokens()
    parser.feed(html)
    tokens = parser.tokens
    anchors = [(href, text) for kind, href, text in tokens if kind == "a" and href.strip()]
    on_host = []
    for href, text in anchors:
        absolute = urldefrag(urljoin(target.url, href.strip()))[0]
        host = urlsplit(absolute).hostname
        if host and _host_in_domain(host, target.host_suffix):
            on_host.append((absolute, text))
    with_prefix = [a for a in on_host if not target.item_url_prefixes or a[0].startswith(target.item_url_prefixes)]
    dated = [a for a in with_prefix if parse_date(a[1])]
    titled = [a for a in with_prefix if len(_strip_trailing_date(a[1])) >= target.min_title_chars]
    listing = urldefrag(target.url)[0]
    below = [a for a in on_host if a[0].startswith(listing) and a[0] != listing]
    lines = [
        f"{len(anchors)} anchors, {len(on_host)} on {target.host_suffix}, {len(with_prefix)} under the item prefix, "
        f"{len(titled)} with a title of {target.min_title_chars}+ chars, {len(dated)} with a date in the link text",
        f"{len(html)} bytes of HTML, {html.lower().count('<script')} script tags, {html.lower().count('<table')} tables",
    ]
    lines += [f"first link: {text[:60]!r} -> {url}" for url, text in on_host[:limit]]
    lines.append(f"{len(below)} links sit under the listing path")
    lines += [f"under listing: {text[:60]!r} -> {url}" for url, text in below[:limit]]

    def neighbour(start: int, step: int) -> str:
        for j in range(start, start + 4 * step, step):
            if 0 <= j < len(tokens) and tokens[j][0] == "a" and tokens[j][1].strip():
                return urldefrag(urljoin(target.url, tokens[j][1].strip()))[0]
        return "-"

    shown = 0
    for index, (kind, _href, text) in enumerate(tokens):
        if kind == "t" and parse_date(text) and shown < 5:
            lines.append(f"dated text: {text[:50]!r} before={neighbour(index - 1, -1)} after={neighbour(index + 1, 1)}")
            around = []
            for tok_kind, tok_href, tok_text in tokens[index + 1 : index + 5]:
                around.append(f"a[{tok_text[:40]!r} -> {tok_href[-48:]}]" if tok_kind == "a" else f"t[{tok_text[:60]!r}]")
            lines.append(f"    next tokens: {' '.join(around)}")
            shown += 1
    return lines


def drop_flagged(items: Iterable[Item]) -> tuple[list[Item], int]:
    """Third-party link text ends up in front of reviewers and, once approved,
    possibly in answers: apply the same injection scan every ingestion path uses."""
    kept: list[Item] = []
    flagged = 0
    for item in items:
        if _scan_for_injection(item.title):
            flagged += 1
        else:
            kept.append(item)
    return kept, flagged


@dataclass(frozen=True)
class ScanPlan:
    rows: list[dict[str, Any]]
    status: str  # baseline | pending | none
    suspicious: bool = False


def plan_scan(target: WatchTarget, items: Sequence[Item], existing: Optional[dict[str, str]]) -> ScanPlan:
    """What to write for one target. `existing` maps item_url -> status; None
    means the queue is unreachable and the caller is only reporting."""
    def row(item: Item, status: str) -> dict[str, Any]:
        return {
            "target_name": target.name,
            "item_url": item.url,
            "title": item.title,
            "published_on": item.published_on.isoformat() if item.published_on else None,
            "status": status,
        }

    if not existing:
        return ScanPlan(rows=[row(i, "baseline") for i in items], status="baseline" if items else "none")
    fresh = [i for i in items if i.url not in existing]
    if len(fresh) > MAX_NEW_PER_TARGET:
        return ScanPlan(rows=[], status="none", suspicious=True)
    return ScanPlan(rows=[row(i, "pending") for i in fresh], status="pending" if fresh else "none")


# ── Supabase layer ──────────────────────────────────────────────────────────


def _api_error_code(exc: Exception) -> str:
    code = getattr(exc, "code", None)
    if code:
        return str(code)
    return str(exc.args[0].get("code", "")) if exc.args and isinstance(exc.args[0], dict) else ""


def _guard_queue(exc: Exception) -> Exception:
    if _api_error_code(exc) in _TABLE_MISSING_CODES or "does not exist" in str(exc) or "schema cache" in str(exc):
        return QueueUnavailable(str(exc))
    return exc


def make_client() -> Optional[Any]:
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        return None
    from supabase import create_client

    return create_client(url, key)


def load_existing(client: Any, target_name: str) -> dict[str, str]:
    existing: dict[str, str] = {}
    start = 0
    while True:
        try:
            page = (
                client.table(TABLE)
                .select("item_url,status")
                .eq("target_name", target_name)
                .range(start, start + _PAGE_SIZE - 1)
                .execute()
            )
        except Exception as exc:
            raise _guard_queue(exc) from exc
        existing.update({r["item_url"]: r["status"] for r in page.data or []})
        if len(page.data or []) < _PAGE_SIZE:
            return existing
        start += _PAGE_SIZE


def write_rows(client: Any, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    try:
        # ignore_duplicates: two overlapping scans can never double-queue an item.
        client.table(TABLE).upsert(rows, on_conflict="target_name,item_url", ignore_duplicates=True).execute()
    except Exception as exc:
        raise _guard_queue(exc) from exc


# ── scan ────────────────────────────────────────────────────────────────────


def scan_target(target: WatchTarget, client: Optional[Any], dry_run: bool, fetch=fetch_feed) -> dict[str, Any]:
    """One target end to end. Never raises for a bad site: the result says what happened."""
    result: dict[str, Any] = {"target": target.name, "url": target.url, "state": "ok", "found": 0, "flagged": 0, "written": 0}
    try:
        html = fetch(target.url, target.host_suffix).decode("utf-8", errors="replace")
    except httpx.HTTPError as exc:
        result.update(state="fetch_failed", detail=f"{type(exc).__name__}: {str(exc)[:120]}")
        return result

    items, flagged = drop_flagged(extract_items(html, target))
    result.update(found=len(items), flagged=flagged, dated=sum(1 for i in items if i.published_on), sample=items[:5])
    if not items:
        result.update(
            state="no_items",
            detail="page parsed but no item links matched; the layout may have changed",
            diagnostics=diagnose(html, target),
        )
        return result

    existing: Optional[dict[str, str]] = None
    if client is not None:
        try:
            existing = load_existing(client, target.name)
        except QueueUnavailable:
            result["state"] = "queue_unavailable"
            return result
    plan = plan_scan(target, items, existing if client is not None else None)
    result["plan"] = plan.status
    if plan.suspicious:
        result.update(state="suspicious", detail=f"more than {MAX_NEW_PER_TARGET} new links at once; nothing queued")
        return result
    if dry_run or client is None:
        result["would_write"] = len(plan.rows)
        return result
    try:
        write_rows(client, plan.rows)
    except QueueUnavailable:
        result["state"] = "queue_unavailable"
        return result
    result["written"] = len(plan.rows)
    return result


def run_scan(names: Sequence[str], dry_run: bool, client: Optional[Any]) -> int:
    targets = [TARGETS_BY_NAME[n] for n in names] if names else list(TARGETS)
    results = [scan_target(t, client, dry_run) for t in targets]
    for r in results:
        line = f"{r['target']}: {r['state']}, {r['found']} items ({r.get('dated', 0)} dated)"
        if r.get("plan"):
            line += f", plan={r['plan']}"
        if r.get("written"):
            line += f", wrote {r['written']}"
        if r.get("would_write") is not None:
            line += f", would write {r['would_write']}"
        if r.get("flagged"):
            line += f", skipped {r['flagged']} flagged by the injection scan"
        if r.get("detail"):
            line += f" ({r['detail']})"
        print(line)
        for note in r.get("diagnostics", []):
            print(f"    {note}")
        for item in r.get("sample", []):
            print(f"    {item.published_on or '----------'}  {item.title[:90]}  {item.url}")
    if any(r["state"] == "queue_unavailable" for r in results):
        print(f"\nThe review queue table does not exist yet. Paste {MIGRATION_FILE} into the Supabase SQL editor, then rerun.")
    if client is None and not dry_run:
        print("\nSUPABASE_URL / SUPABASE_SERVICE_KEY not set: ran as a dry run.")
    return 0 if any(r["state"] in ("ok", "queue_unavailable", "suspicious", "no_items") for r in results) else 1


# ── review ──────────────────────────────────────────────────────────────────


def list_items(client: Any, status: str, target: Optional[str], limit: int) -> list[dict[str, Any]]:
    query = client.table(TABLE).select("id,target_name,title,item_url,published_on,first_seen_at,status").eq("status", status)
    if target:
        query = query.eq("target_name", target)
    try:
        return query.order("first_seen_at", desc=True).limit(limit).execute().data or []
    except Exception as exc:
        raise _guard_queue(exc) from exc


def review_items(client: Any, ids: Sequence[str], decision: str, note: Optional[str]) -> int:
    """Only `pending` rows can be decided, so a repeated or stale command is a no-op."""
    from datetime import datetime, timezone

    status = {"approve": "approved", "reject": "rejected"}[decision]
    update = {"status": status, "reviewed_at": datetime.now(timezone.utc).isoformat(), "review_note": (note or None)}
    try:
        res = client.table(TABLE).update(update).in_("id", list(ids)).eq("status", "pending").execute()
    except Exception as exc:
        raise _guard_queue(exc) from exc
    return len(res.data or [])


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    scan = sub.add_parser("scan", help="fetch listing pages and queue new items")
    scan.add_argument("--target", action="append", default=[], help="target name (repeatable; default all)")
    scan.add_argument("--dry-run", action="store_true", help="print what would be queued; write nothing")

    lst = sub.add_parser("list", help="show queued items")
    lst.add_argument("--status", default="pending", choices=["baseline", "pending", "approved", "rejected"])
    lst.add_argument("--target")
    lst.add_argument("--limit", type=int, default=50)

    rev = sub.add_parser("review", help="approve or reject pending items")
    rev.add_argument("decision", choices=["approve", "reject"])
    rev.add_argument("ids", nargs="+")
    rev.add_argument("--note", help="short reason (max 500 chars)")

    args = parser.parse_args(argv)

    if args.command == "scan":
        unknown = [n for n in args.target if n not in TARGETS_BY_NAME]
        if unknown:
            print(f"unknown target(s): {', '.join(unknown)}", file=sys.stderr)
            return 2
        return run_scan(args.target, args.dry_run, None if args.dry_run else make_client())

    client = make_client()
    if client is None:
        print("SUPABASE_URL and SUPABASE_SERVICE_KEY are required for this command.", file=sys.stderr)
        return 2
    try:
        if args.command == "list":
            for row in list_items(client, args.status, args.target, args.limit):
                print(f"{row['id']}  {row.get('published_on') or '----------'}  [{row['target_name']}]  {row['title'][:80]}\n    {row['item_url']}")
            return 0
        if args.note and len(args.note) > 500:
            print("--note must be 500 characters or fewer", file=sys.stderr)
            return 2
        changed = review_items(client, args.ids, args.decision, args.note)
        print(f"{args.decision}d {changed} of {len(args.ids)} item(s) (only pending items can be decided)")
        return 0
    except QueueUnavailable:
        print(f"The review queue table does not exist yet. Paste {MIGRATION_FILE} into the Supabase SQL editor.", file=sys.stderr)
        return 3


if __name__ == "__main__":  # CLI script: print is the interface here
    sys.exit(main())
