"""Source-specific HTML extractors for ingest_feed.

The generic extractor (ingest_feed.extract_blocks) keeps every visible block of
text longer than a few characters. On LHDN's site that returns the navigation
menu, drops the short cells and list items a rate table is made of, and lets
the menu's "Year of Assessment 2025" link date the chunk. Read from a GitHub
runner with scripts/inspect_page.py, LHDN's content pages are Elementor
accordions: one <details> per year of assessment (or per topic), holding either
a real <table> (individual rates) or nested <ul>/<li> lists with the rate in a
<strong> (company rates). This reads exactly that, one chunk per accordion item.

It fails loudly instead of falling back: a page with no accordion items is a
changed page, and ingesting its menu again is the failure this replaces.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Optional

from bs4 import BeautifulSoup, Tag

_WS = re.compile(r"\s+")
_YEAR = re.compile(r"\b(20\d{2})\b")
_NUMBER = re.compile(r"\d+(?:\.\d+)?")
# Headings that label a section of the site, not the page's own subject.
_GENERIC_HEADINGS = {"company", "individual", "visitor statistics", "individu", "syarikat", ""}


class ExtractionError(RuntimeError):
    """The page does not have the structure this extractor reads."""


@dataclass
class ExtractedItem:
    title: str
    text: str
    valid_from: Optional[date] = None
    valid_until: Optional[date] = None


def _clean(text: str) -> str:
    return _WS.sub(" ", text).strip()


def _cell_text(cell: Tag) -> str:
    return _clean(cell.get_text(" ", strip=True))


def _marginal_rate(cell: str) -> Optional[str]:
    """LHDN's Rate cell holds one number per sub-band ("– 1" for a band that is
    nothing on the first slice and 1% on the next); the last number is the rate
    for the income range the row is about."""
    numbers = _NUMBER.findall(cell)
    return numbers[-1] if numbers else None


def _is_income_header(header: str) -> bool:
    return bool(re.search(r"income|range", header, re.IGNORECASE))


def _is_rate_header(header: str) -> bool:
    return bool(re.match(r"\s*rate", header, re.IGNORECASE))


def _render_grid_table(rows: list[list[str]]) -> Optional[list[str]]:
    """A table with a spanning group header over a row of column labels, such as LHDN's RPGT rates:

        Holding Period | Disposal Date                        (spans every column below)
                       | 1.1.2019 to 31.12.2021 | Starting from the 1.1.2022
        Within 2 years | 30%                    | 30%

    Read cell by cell against the first-row header, "30%" would be labelled "Disposal Date" and
    the period it belongs to lost. Returns None when the table is not this shape.
    """
    if len(rows) < 3 or len(rows[0]) > 2:
        return None
    labels = [c for c in rows[1] if c]
    body = rows[2:]
    if len(labels) < 2 or any(len(r) != len(labels) + 1 for r in body):
        return None
    row_name = rows[0][0]
    group = rows[0][1] if len(rows[0]) > 1 else ""
    lines: list[str] = []
    for row in body:
        cells = "; ".join(f"{group} {label}: {value}".strip() for label, value in zip(labels, row[1:]) if value)
        lines.append(f"{row_name} {row[0]}: {cells}".strip())
    return lines


def render_table(table: Tag) -> list[str]:
    """One line per row, every cell labelled with its column header, so a figure
    is never separated from what it is a figure of. Rate tables (an income
    column and a rate column) lead with "income range: rate N%"."""
    rows = [[_cell_text(c) for c in tr.find_all(["th", "td"])] for tr in table.find_all("tr")]
    rows = [r for r in rows if any(r)]
    if len(rows) < 2:
        return [" | ".join(r) for r in rows]
    grid = _render_grid_table(rows)
    if grid is not None:
        return grid
    headers, body = rows[0], rows[1:]
    income_i = next((i for i, h in enumerate(headers) if _is_income_header(h)), None)
    rate_i = next((i for i, h in enumerate(headers) if _is_rate_header(h)), None)
    lines: list[str] = []
    for row in body:
        row = row + [""] * (len(headers) - len(row))
        if income_i is not None and rate_i is not None and row[rate_i]:
            rate = _marginal_rate(row[rate_i])
            head = f"{headers[income_i]} {row[income_i]}: rate {rate}%" if rate else f"{headers[income_i]} {row[income_i]}"
            rest = "; ".join(
                f"{h}: {v}" for i, (h, v) in enumerate(zip(headers, row)) if i not in (income_i, rate_i) and v
            )
            lines.append(f"{head} ({rest})" if rest else head)
        else:
            lines.append("; ".join(f"{h}: {v}" for h, v in zip(headers, row) if v))
    return lines


def render_node(node: Tag, depth: int = 0) -> list[str]:
    """Text with structure kept: tables as labelled rows, list items as an
    indented outline (the nesting says which sub-band a rate belongs to)."""
    lines: list[str] = []
    for child in node.children:
        if isinstance(child, Tag):
            if child.name == "table":
                lines.extend("  " * depth + line for line in render_table(child))
            elif child.name in ("ul", "ol"):
                lines.extend(render_node(child, depth))
            elif child.name == "li":
                own_parts = [
                    _cell_text(c) if isinstance(c, Tag) else str(c)
                    for c in child.children
                    if not (isinstance(c, Tag) and c.name in ("ul", "ol", "table"))
                ]
                own = _clean(" ".join(own_parts))
                if own:
                    lines.append("  " * depth + "- " + own)
                for nested in child.find_all(["ul", "ol", "table"], recursive=False):
                    if nested.name == "table":
                        lines.extend("  " * (depth + 1) + line for line in render_table(nested))
                    else:
                        lines.extend(render_node(nested, depth + 1))
            else:
                lines.extend(render_node(child, depth))
        else:
            text = _clean(str(child))
            if text:
                lines.append("  " * depth + text)
    return lines


def _years(title: str) -> list[int]:
    return [int(y) for y in _YEAR.findall(title)]


def _page_heading(soup: BeautifulSoup, fallback: str) -> str:
    for h in soup.find_all(["h1", "h2"]):
        text = _clean(h.get_text(" ", strip=True))
        if text.lower() not in _GENERIC_HEADINGS and not re.fullmatch(r"[\d,\s]+", text):
            return text
    return fallback


def parse_lhdn_accordion(html: str, fallback_title: str) -> list[ExtractedItem]:
    """One ExtractedItem per top-level accordion item (<details>) on an LHDN page.

    A year-of-assessment item is dated from its own title: valid_from is 1 January
    of the earliest year it names; valid_until is 31 December of the latest year
    it names ONLY when the same page publishes a later year (the table was
    replaced), so the newest table stays current until LHDN publishes another.
    Items whose title names no year get no dates: the text is never scanned for
    them here (a menu link naming "Year of Assessment 2025" once expired a chunk).
    """
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    details = [d for d in soup.find_all("details") if not d.find_parent("details")]
    if not details:
        raise ExtractionError("no accordion items (<details>) found: the page structure changed")

    # A label the registry gave the source ("Individual Income Tax Rates (LHDN)") is what
    # a citation should say; the page's own heading ("Tax Rate") does not say whose.
    # Only when the caller had nothing better than a URL is the page's heading used.
    page = fallback_title if fallback_title and not fallback_title.startswith("http") else _page_heading(soup, fallback_title)
    parsed: list[tuple[str, list[str], list[int]]] = []
    for d in details:
        summary = d.find("summary")
        title = _clean(summary.get_text(" ", strip=True)) if summary else ""
        if summary:
            summary.extract()
        lines = render_node(d)
        if not lines:
            continue
        parsed.append((title, lines, _years(title)))
    if not parsed:
        raise ExtractionError("accordion items found but all were empty")

    newest = max((max(ys) for _, _, ys in parsed if ys), default=None)
    items: list[ExtractedItem] = []
    for title, lines, years in parsed:
        valid_from = date(min(years), 1, 1) if years else None
        valid_until = date(max(years), 12, 31) if years and newest and max(years) < newest else None
        label = f"{page} — {title}" if title else page
        items.append(ExtractedItem(title=label, text="\n".join(lines), valid_from=valid_from, valid_until=valid_until))
    return items


_CONTENT_MIN_CHARS = 80


_LAST_UPDATED = re.compile(r"^\s*last updated on\b", re.IGNORECASE)
_LEADING_NUMBER = re.compile(r"^\s*\d+[.)]\s*")


def _own_text(el: Tag) -> str:
    parts = [
        _cell_text(c) if isinstance(c, Tag) else str(c)
        for c in el.children
        if not (isinstance(c, Tag) and c.name in ("ul", "ol", "table"))
    ]
    return _clean(" ".join(parts))


def _content_flow(widget: Tag) -> list[tuple[str, object]]:
    """The widget's paragraphs, list items and tables in document order. Elements nested in a table
    cell or in another list item are skipped: they are rendered with their parent."""
    flow: list[tuple[str, object]] = []
    for el in widget.find_all(["p", "li", "table"]):
        if el.find_parent("table") is not None and el.name != "table":
            continue
        if el.name == "table" and el.find_parent("table") is not None:
            continue
        if el.name == "li" and el.find_parent("li") is not None:
            continue
        if el.name == "table":
            flow.append(("table", el))
        else:
            # An <li> can hold the table it introduces ("5. RPGT rate for ...:" then the table), so its
            # text is its OWN text: get_text() would fold every table cell into the caption.
            text = _own_text(el) if el.name == "li" else _clean(el.get_text(" ", strip=True))
            if text and not _LAST_UPDATED.match(text):
                flow.append(("text", f"- {text}" if el.name == "li" else text))
    return flow


def parse_lhdn_content(html: str, fallback_title: str) -> list[ExtractedItem]:
    """An LHDN page whose content is plain text-editor widgets, not accordions (e.g. RPGT rates).

    One ExtractedItem per table, with the sentence just above it kept in the same chunk and named
    in its title ("... Part I Schedule 5 RPGTA"), so a chunk that is split or retrieved alone still
    says which disposer its rates are for. Other paragraphs become their own chunks. No dates are read
    from the text: such a page quotes many past dates and ends in "Last updated on ...", none of
    which is a validity window.
    """
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav"]):
        tag.decompose()
    widgets = [w for w in soup.select("div.elementor-widget-text-editor") if not w.find_parent(class_="elementor-widget-text-editor")]
    if not widgets:
        raise ExtractionError("no text-editor content widgets found: the page structure changed")
    page = fallback_title if fallback_title and not fallback_title.startswith("http") else _page_heading(soup, fallback_title)

    items: list[ExtractedItem] = []

    def add(title: str, lines: list[str]) -> None:
        text = "\n".join(lines)
        if len(text) >= _CONTENT_MIN_CHARS:
            items.append(ExtractedItem(title=title, text=text))

    for widget in widgets:
        pending: list[str] = []
        for kind, value in _content_flow(widget):
            if kind == "text":
                pending.append(str(value))
                continue
            rows = render_table(value)  # type: ignore[arg-type]
            caption = pending[-1] if pending else ""
            if pending[:-1]:
                add(page, pending[:-1])
            label = _LEADING_NUMBER.sub("", caption.removeprefix("- ")).rstrip(": ")
            add(f"{page} — {label}" if label else page, ([caption] if caption else []) + rows)
            pending = []
        if pending:
            add(page, pending)
    if not items:
        raise ExtractionError("content widgets found but all were empty")
    return items


def parse_eael_accordion(html: str, fallback_title: str) -> list[ExtractedItem]:
    """One ExtractedItem per item of an Essential Addons accordion (the Customs MySST pages).

    Title is the item's own heading (a question, or a registration category); content keeps its
    tables as labelled rows. No dates: these pages state current rules, not validity windows.
    """
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav"]):
        tag.decompose()
    entries = soup.select("div.eael-accordion-list")
    if not entries:
        raise ExtractionError("no accordion items (eael-accordion-list) found: the page structure changed")
    page = fallback_title if fallback_title and not fallback_title.startswith("http") else _page_heading(soup, fallback_title)
    items: list[ExtractedItem] = []
    for entry in entries:
        title_tag = entry.select_one(".eael-accordion-tab-title")
        content = entry.select_one(".eael-accordion-content")
        if content is None:
            continue
        lines = render_node(content)
        text = "\n".join(lines)
        if len(text) < _CONTENT_MIN_CHARS // 2:
            continue
        title = _clean(title_tag.get_text(" ", strip=True)) if title_tag else ""
        items.append(ExtractedItem(title=f"{page} — {title}" if title else page, text=text))
    if not items:
        raise ExtractionError("accordion items found but all were empty")
    return items


EXTRACTORS = {
    "lhdn_accordion": parse_lhdn_accordion,
    "lhdn_content": parse_lhdn_content,
    "eael_accordion": parse_eael_accordion,
}
