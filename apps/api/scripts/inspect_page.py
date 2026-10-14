#!/usr/bin/env python3
"""Print the structure of a web page, to write a source-specific extractor against.

ingest_feed's generic HTML extraction keeps every visible block of text, so a
site whose navigation is long (LHDN's) comes out as menu text and a rate table
can lose its numbers. Fixing that needs the page's real markup, and the build
sandbox cannot reach most government sites, so this runs from a GitHub runner
(.github/workflows/inspect-page.yml) and prints a compact report instead of the
whole page:

  - the <title> and headings
  - the largest text containers (tag#id.class, text length, digit count), which
    is how the main content area is told apart from the navigation
  - every <table>: how many rows, whether it has numbers, and its first rows
  - where given --find phrases occur, the chain of ancestors up to <body>

Usage:
    python -m scripts.inspect_page URL [--find "paid up capital" --find "RM5,000"]
"""
from __future__ import annotations

import argparse
import re
import sys

import httpx
from bs4 import BeautifulSoup, Tag

_WS = re.compile(r"\s+")


def _label(el: Tag) -> str:
    ident = f"#{el['id']}" if el.get("id") else ""
    classes = "".join(f".{c}" for c in (el.get("class") or [])[:4])
    return f"{el.name}{ident}{classes}"


def _text(el: Tag) -> str:
    return _WS.sub(" ", el.get_text(" ", strip=True))


def _digits(s: str) -> int:
    return sum(ch.isdigit() for ch in s)


def container_report(soup: BeautifulSoup, top: int = 12) -> list[str]:
    rows = []
    for el in soup.find_all(["main", "article", "section", "div", "form", "nav", "header", "footer", "aside"]):
        text = _text(el)
        if len(text) < 200:
            continue
        rows.append((len(text), _digits(text), _label(el), len(el.find_all("table"))))
    rows.sort(reverse=True)
    out = []
    for length, digits, label, tables in rows[:top]:
        out.append(f"  {length:>6} chars {digits:>5} digits {tables:>2} tables  {label}")
    return out


def table_report(soup: BeautifulSoup, max_tables: int = 12, max_rows: int = 6) -> list[str]:
    out = []
    for i, table in enumerate(soup.find_all("table")[:max_tables]):
        trs = table.find_all("tr")
        text = _text(table)
        parent = _label(table.parent) if isinstance(table.parent, Tag) else "?"
        out.append(f"  table[{i}] in {parent}: {len(trs)} rows, {len(text)} chars, {_digits(text)} digits")
        for tr in trs[:max_rows]:
            cells = [_text(c)[:40] for c in tr.find_all(["th", "td"])]
            out.append("      | " + " | ".join(cells))
    return out


def find_report(soup: BeautifulSoup, phrases: list[str]) -> list[str]:
    out = []
    for phrase in phrases:
        needle = phrase.lower()
        hits = [t for t in soup.find_all(string=True) if needle in str(t).lower()]
        out.append(f"  {phrase!r}: {len(hits)} text node(s)")
        for node in hits[:3]:
            chain = []
            el = node.parent
            while isinstance(el, Tag) and el.name != "[document]":
                chain.append(_label(el))
                el = el.parent
            out.append("      " + " < ".join(chain[:8]))
            out.append(f"      text: {_WS.sub(' ', str(node)).strip()[:120]!r}")
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("url")
    parser.add_argument("--find", action="append", default=[], help="phrase to locate (repeatable)")
    args = parser.parse_args(argv)

    resp = httpx.get(args.url, timeout=30.0, follow_redirects=True, headers={"User-Agent": "NakTahu-FeedIngest/1.0"})
    print(f"GET {args.url} -> {resp.status_code}, {len(resp.content)} bytes, final url {resp.url}")
    resp.raise_for_status()
    soup = BeautifulSoup(resp.content, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    print(f"title: {soup.title.get_text(strip=True) if soup.title else None!r}")
    print("headings:")
    for h in soup.find_all(["h1", "h2", "h3"])[:25]:
        print(f"  {h.name}: {_text(h)[:90]!r}  ({_label(h.parent) if isinstance(h.parent, Tag) else '?'})")
    print("largest containers (content vs navigation):")
    print("\n".join(container_report(soup)))
    print("tables:")
    tables = table_report(soup)
    print("\n".join(tables) if tables else "  (none)")
    if args.find:
        print("phrases:")
        print("\n".join(find_report(soup, args.find)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
