"""The LHDN accordion extractor, against markup shaped like the real pages.

The figures are the rows scripts/inspect_page.py printed from hasil.gov.my on
2026-10-14 (a GitHub runner; the build sandbox cannot reach the site). The
failure they guard against: the generic extractor ingested the navigation menu,
dropped the table's numbers, and dated the chunk from a menu link.
"""
from __future__ import annotations

import argparse
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from scripts.html_extractors import EXTRACTORS, ExtractionError, parse_lhdn_accordion
from scripts.ingest_feed import FeedEntry, date_fields, main_async, parse_html_page
from scripts.sources import SOURCES_BY_NAME

_NAV = (
    "<nav><a>Automatic Exchange of Information (AEOI)</a> <a>Double Taxation Avoidance Agreement</a> "
    "<a>Filing Programme For Return Of Profits By A Labuan Entity For The Year Of Assessment 2025</a></nav>"
)
_STATS = '<div class="lh_visitor_footer"><h2>Visitor Statistics</h2><h3>26,188</h3><h3>1,701,436</h3></div>'


def _table(header: list[str], rows: list[list[str]]) -> str:
    head = "".join(f"<th>{h}</th>" for h in header)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<div class="table-wrapper"><table class="custom-table"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


_NEW_ROWS = [
    ["A", "0 – 5,000", "On the First 5000", "0", "0"],
    ["B", "5,001 – 20,000", "On the First 5000 Next 15,000", "– 1", "0 150"],
    ["F", "70,001 – 100,000", "On the First 70,000 Next 30,000", "– 19", "3,700 5,700"],
    ["I", "600,001 – 2,000,000", "On the First 600,000 Next 1,400,000", "– 28", "136,400 392,000"],
    ["J", "Exceeding 2,000,000", "On the First 2,000,000 Next ringgit", "– 30", "528,400 –"],
]
_OLD_ROWS = [
    ["A", "0 – 5,000", "On the First 5000", "0", "0"],
    ["F", "70,001 – 100,000", "On the First 70,000 Next 30,000", "– 21", "4,400 6,300"],
    ["G", "100,001 – 250,000", "On the First 100,000 Next 150,000", "– 24", "10,700 36,000"],
]
_HEAD = ["Category", "Chargeable Income (RM)", "Calculation (RM)", "Rate %", "Tax (RM)"]

INDIVIDUAL_PAGE = f"""<html><head><title>Kadar Cukai</title></head><body>{_NAV}
<h2>Tax Rate</h2>
<div class="e-n-accordion">
<details class="e-n-accordion-item"><summary><span>Year of Assessment 2023, 2024 &amp; 2025</span></summary>
 <div>{_table(_HEAD, _NEW_ROWS)}</div></details>
<details class="e-n-accordion-item"><summary><span>Year of Assessment 2022</span></summary>
 <div>{_table(_HEAD, _OLD_ROWS)}</div></details>
</div>{_STATS}</body></html>"""

COMPANY_PAGE = f"""<html><head><title>Kadar Cukai Syarikat</title></head><body>{_NAV}
<h2>Company</h2><h2>Tax Rate of Company</h2>
<div class="e-n-accordion">
<details class="e-n-accordion-item"><summary>Year Assessment 2023 - 2024</summary><div><ul>
 <li>Company with paid up capital not more than RM2.5 million and gross business income of not more than RM50 million
   <ul><li>On first RM150,000 <strong>(15%)</strong></li><li>RM150,001 to RM600,000 <strong>(17%)</strong></li>
   <li>RM600,001 and Subsequent Balance <strong>(24%)</strong></li></ul></li>
 <li>Company other than the above category <strong>(24%)</strong></li></ul></div></details>
<details class="e-n-accordion-item"><summary>Year Assessment 2020 - 2022</summary><div><ul>
 <li>Company with paid up capital not more than RM2.5 million and gross business income of not more than RM50 million
   <ul><li>On first RM600,000 <strong>(17%)</strong></li><li>Subsequent Balance <strong>(24%)</strong></li></ul></li>
 <li>Company other than the above category <strong>(24%)</strong></li></ul></div></details>
</div>{_STATS}</body></html>"""


def _items(page: str, title: str = "Individual Income Tax Rates (LHDN)"):
    return parse_lhdn_accordion(page, title)


def test_rate_table_keeps_every_band_with_its_rate():
    newest = _items(INDIVIDUAL_PAGE)[0]
    assert "Chargeable Income (RM) 5,001 – 20,000: rate 1%" in newest.text
    assert "Chargeable Income (RM) 70,001 – 100,000: rate 19%" in newest.text
    assert "Chargeable Income (RM) 600,001 – 2,000,000: rate 28%" in newest.text
    assert "Chargeable Income (RM) Exceeding 2,000,000: rate 30%" in newest.text
    # The raw calculation and tax cells are kept next to the derived rate.
    assert "Calculation (RM): On the First 5000 Next 15,000" in newest.text


def test_the_navigation_and_visitor_counters_never_reach_a_chunk():
    for page in (INDIVIDUAL_PAGE, COMPANY_PAGE):
        text = " ".join(i.text + i.title for i in _items(page))
        assert "Automatic Exchange of Information" not in text
        assert "Visitor Statistics" not in text and "1,701,436" not in text


def test_each_accordion_item_is_its_own_chunk_titled_with_its_year():
    items = _items(INDIVIDUAL_PAGE)
    assert [i.title for i in items] == [
        "Individual Income Tax Rates (LHDN) — Year of Assessment 2023, 2024 & 2025",
        "Individual Income Tax Rates (LHDN) — Year of Assessment 2022",
    ]
    # With only a URL to go on, the page's own subject heading is used instead.
    assert _items(COMPANY_PAGE, "https://www.hasil.gov.my/x")[0].title == "Tax Rate of Company — Year Assessment 2023 - 2024"


def test_the_newest_table_stays_current_and_older_tables_are_closed():
    newest, older = _items(INDIVIDUAL_PAGE)
    assert (newest.valid_from, newest.valid_until) == (date(2023, 1, 1), None)
    assert (older.valid_from, older.valid_until) == (date(2022, 1, 1), date(2022, 12, 31))
    c_new, c_old = _items(COMPANY_PAGE)
    assert (c_new.valid_from, c_new.valid_until) == (date(2023, 1, 1), None)
    assert (c_old.valid_from, c_old.valid_until) == (date(2020, 1, 1), date(2022, 12, 31))


def test_company_sme_tiers_keep_their_nesting():
    text = _items(COMPANY_PAGE)[0].text.splitlines()
    assert text[0].startswith("- Company with paid up capital not more than RM2.5 million")
    assert "  - On first RM150,000 (15%)" in text
    assert "  - RM150,001 to RM600,000 (17%)" in text
    assert "  - RM600,001 and Subsequent Balance (24%)" in text
    assert "- Company other than the above category (24%)" in text


def test_a_page_without_accordion_items_fails_instead_of_returning_the_menu():
    with pytest.raises(ExtractionError, match="structure changed"):
        _items(f"<html><body>{_NAV}<p>Some long paragraph of menu-like text " + "x" * 300 + "</p></body></html>")


def test_a_table_without_an_income_and_rate_column_keeps_labelled_cells():
    page = f"""<html><body><h2>SME</h2><div><details><summary>Categories of SME</summary>
    {_table(["Category", "Micro", "Small"], [["Factory", "Sales less than RM300,000", "Sales from RM300,000 to RM15 million"]])}
    </details></div></body></html>"""
    (item,) = _items(page)
    assert "Category: Factory; Micro: Sales less than RM300,000; Small: Sales from RM300,000 to RM15 million" in item.text
    assert (item.valid_from, item.valid_until) == (None, None)


# ── wiring into ingest_feed ───────────────────────────────────────────────────

def test_parse_html_page_with_an_extractor_returns_dated_entries():
    entries = parse_html_page(INDIVIDUAL_PAGE.encode(), "https://www.hasil.gov.my/en/individu/kadar-cukai/", "x", "lhdn_accordion")
    assert len(entries) == 2 and all(e.dates_explicit for e in entries)
    assert all(e.link == "https://www.hasil.gov.my/en/individu/kadar-cukai/" for e in entries)
    assert entries[0].valid_from == date(2023, 1, 1)


def test_explicit_dates_are_used_and_the_text_is_not_scanned_for_dates():
    # The text says "effective from 1 January 2030"; an explicit-dates entry must ignore it.
    entry = FeedEntry(title="t", description="Rate effective from 1 January 2030 until 31 December 2031", link="u",
                      valid_from=date(2023, 1, 1), valid_until=None, dates_explicit=True)
    assert date_fields(entry, argparse.Namespace()) == {"effective_date": "2023-01-01"}
    inferred = FeedEntry(title="t", description=entry.description, link="u")
    assert "effective_date" in date_fields(inferred, argparse.Namespace())


def test_cli_date_overrides_still_win_over_extracted_dates():
    entry = FeedEntry(title="t", description="d", link="u", valid_from=date(2023, 1, 1), dates_explicit=True)
    assert date_fields(entry, argparse.Namespace(effective_date="2026-01-01"))["effective_date"] == "2026-01-01"


def test_the_lhdn_pages_are_registered_with_the_extractor_and_a_citation_title():
    for name in ("lhdn-company-tax-rates", "lhdn-sme-tax", "lhdn-individual-tax-rates"):
        source = SOURCES_BY_NAME[name]
        assert source.extractor in EXTRACTORS
        assert source.title and source.title.endswith("(LHDN)")


def _args(**kw):
    base = dict(feed_url="https://www.hasil.gov.my/en/individu/kadar-cukai/", kind="html", domain="tax",
                ministry="LHDN", language="en", limit=50, dry_run=True, source_title="Individual Income Tax Rates (LHDN)",
                extractor="lhdn_accordion", require_host_suffix=None)
    base.update(kw)
    return MagicMock(**base)


@pytest.mark.asyncio
async def test_dry_run_with_the_extractor_shows_the_rates_in_the_preview(monkeypatch, capsys):
    monkeypatch.setattr("scripts.ingest_feed.fetch_feed", MagicMock(return_value=INDIVIDUAL_PAGE.encode()))
    monkeypatch.setattr("scripts.ingest_feed.embed_for_storage", AsyncMock(return_value={"embedding_v2": [0.0] * 1024}))
    supabase = MagicMock()
    supabase.table.return_value.select.return_value.in_.return_value.execute.return_value.data = []
    monkeypatch.setattr("scripts.ingest_feed.create_client", lambda url, key: supabase)
    await main_async(_args())
    out = capsys.readouterr().out
    assert "Parsed 2 entries" in out
    assert "'effective_date': '2023-01-01'" in out and "'effective_until': '2022-12-31'" in out
    assert "rate 19%" in out or "rate 1%" in out  # the preview shows real figures, not menu text
    assert "Automatic Exchange" not in out


@pytest.mark.asyncio
async def test_dry_run_exits_nonzero_and_writes_nothing_when_the_structure_changed(monkeypatch, capsys):
    monkeypatch.setattr("scripts.ingest_feed.fetch_feed", MagicMock(return_value=b"<html><body><nav>menu</nav></body></html>"))
    monkeypatch.setattr("scripts.ingest_feed.create_client", lambda url, key: MagicMock())
    with pytest.raises(SystemExit) as exc:
        await main_async(_args())
    assert exc.value.code == 1
    assert "Nothing was written" in capsys.readouterr().err
