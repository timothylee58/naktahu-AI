"""The LHDN plain-content and Customs accordion extractors, plus the grid-table renderer.

The RPGT rows are the ones hasil.gov.my served on 2026-11-16 (read with a fetch tool; the build
sandbox cannot reach the site): three disposer categories, each a table whose first row is a spanning
"Disposal Date" group header over a row of column labels. The Customs markup is the structure
scripts/inspect_page.py printed (eael-accordion-list / -tab-title / -content).
"""
from __future__ import annotations

import pytest

from scripts.html_extractors import (
    EXTRACTORS,
    ExtractionError,
    parse_eael_accordion,
    parse_lhdn_accordion_current,
    parse_lhdn_content,
    render_table,
)
from scripts.ingest_feed import parse_html_page

_NAV = "<nav><a>Filing Programme For The Year Of Assessment 2025</a></nav>"
_FOOTER = "<footer>HASiL Contact Centre 603-8911 1000</footer>"
_STATS = '<div class="lh_visitor_footer"><h2>Visitor Statistics</h2><h3>36,090,188</h3></div>'

RPGT_PAGE = f"""<html><body>{_NAV}
<h2>RPGT</h2><h1>Real Property Gains Tax (RPGT) Rates</h1>
<div class="elementor-widget elementor-widget-text-editor"><div class="table-wrapper">
<p>1. RPGT rates differ according to disposer categories and holding period of chargeable asset.</p>
<p>5. RPGT rate for a disposer under Part I Schedule 5 RPGTA:</p>
<table>
<tr><td>Holding Period</td><td colspan="6">Disposal Date</td></tr>
<tr><td></td><td>1.1.2014 to 31.12.2018</td><td>1.1.2019 to 31.12.2021</td><td>Starting from the 1.1.2022</td></tr>
<tr><td>Within 2 years</td><td>30%</td><td>30%</td><td>30%</td></tr>
<tr><td>In the 3rd year</td><td>30%</td><td>30%</td><td>30%</td></tr>
<tr><td>In the 4th year</td><td>20%</td><td>20%</td><td>20%</td></tr>
<tr><td>In the 5th year</td><td>15%</td><td>15%</td><td>15%</td></tr>
<tr><td>In the 6th year and thereafter</td><td>0%</td><td>5%</td><td>0%</td></tr>
</table>
<p>6. RPGT rate for a disposer under Part II Schedule 5 RPGTA:</p>
<table>
<tr><td>Holding Period</td><td colspan="4">Disposal Date</td></tr>
<tr><td></td><td>1.1.2014 to 31.12.2018</td><td>Mulai 1.1.2019</td></tr>
<tr><td>Within 2 years</td><td>30%</td><td>30%</td></tr>
<tr><td>In the 6th year and thereafter</td><td>5%</td><td>10%</td></tr>
</table>
<p>Last updated on: 23/06/2026 02:56 PM</p>
</div></div>{_STATS}{_FOOTER}</body></html>"""


def test_each_rpgt_table_is_its_own_chunk_titled_by_the_sentence_above_it() -> None:
    items = parse_lhdn_content(RPGT_PAGE, "Real Property Gains Tax Rates (LHDN)")
    assert [i.title for i in items] == [
        "Real Property Gains Tax Rates (LHDN)",
        "Real Property Gains Tax Rates (LHDN) — RPGT rate for a disposer under Part I Schedule 5 RPGTA",
        "Real Property Gains Tax Rates (LHDN) — RPGT rate for a disposer under Part II Schedule 5 RPGTA",
    ]
    part_one = items[1].text
    assert part_one.startswith("5. RPGT rate for a disposer under Part I Schedule 5 RPGTA:")
    # Each rate stays with its holding period and the disposal-date column it belongs to.
    two_years = next(line for line in part_one.splitlines() if "Within 2 years" in line)
    assert two_years.endswith("Disposal Date Starting from the 1.1.2022: 30%")
    fourth = next(line for line in part_one.splitlines() if "In the 4th year" in line)
    assert "Disposal Date 1.1.2014 to 31.12.2018: 20%" in fourth
    sixth = next(line for line in part_one.splitlines() if "6th year" in line)
    assert "Disposal Date 1.1.2019 to 31.12.2021: 5%" in sixth and sixth.endswith("1.1.2022: 0%")


def test_part_two_keeps_its_own_6th_year_rate_apart_from_part_one() -> None:
    part_two = parse_lhdn_content(RPGT_PAGE, "RPGT")[2].text
    assert "Part II Schedule 5" in part_two and "Mulai 1.1.2019: 10%" in part_two
    assert "Part I Schedule" not in part_two.replace("Part II Schedule", "")


def test_navigation_footer_and_visitor_counters_never_reach_the_chunk() -> None:
    text = "\n".join(i.text for i in parse_lhdn_content(RPGT_PAGE, "RPGT"))
    assert "Last updated on" not in text
    for noise in ("Filing Programme", "Contact Centre", "Visitor Statistics", "36,090,188"):
        assert noise not in text


def test_a_two_column_table_is_still_rendered_cell_by_cell() -> None:
    from bs4 import BeautifulSoup

    table = BeautifulSoup("<table><tr><th>Relief</th><th>Amount (RM)</th></tr><tr><td>Spouse</td><td>4,000</td></tr></table>", "html.parser").table
    assert render_table(table) == ["Relief: Spouse; Amount (RM): 4,000"]


def test_lhdn_content_fails_loudly_when_the_page_has_no_content_widgets() -> None:
    with pytest.raises(ExtractionError):
        parse_lhdn_content("<html><body><nav>menu</nav><p>nothing</p></body></html>", "x")


_SST_PAGE = """<html><body><nav>menu</nav>
<div class="eael-accordion-list"><div><span class="eael-accordion-tab-title">Manufacturers</span></div>
<div class="eael-accordion-content"><p>A manufacturer must register for sales tax when the total value of taxable goods sold reaches the threshold.</p>
<table><tr><th>Category</th><th>Threshold</th></tr><tr><td>Sales tax, manufacturer</td><td>RM500,000</td></tr></table></div></div>
<div class="eael-accordion-list"><div><span class="eael-accordion-tab-title">Food and beverage</span></div>
<div class="eael-accordion-content"><p>Food and beverage operators must register for service tax above RM1,500,000 in 12 months.</p></div></div>
</body></html>"""


def test_eael_accordion_gives_one_chunk_per_item_titled_by_its_own_heading() -> None:
    items = parse_eael_accordion(_SST_PAGE, "SST Registering a Business (Customs)")
    assert [i.title for i in items] == [
        "SST Registering a Business (Customs) — Manufacturers",
        "SST Registering a Business (Customs) — Food and beverage",
    ]
    assert "Category: Sales tax, manufacturer; Threshold: RM500,000" in items[0].text
    assert "RM1,500,000" in items[1].text
    assert all(i.valid_from is None and i.valid_until is None for i in items)


def test_eael_accordion_fails_loudly_without_items() -> None:
    with pytest.raises(ExtractionError):
        parse_eael_accordion("<html><body><p>x</p></body></html>", "x")


def test_both_extractors_are_registered_and_reachable_through_parse_html_page() -> None:
    assert {"lhdn_content", "eael_accordion"} <= set(EXTRACTORS)
    entries = parse_html_page(RPGT_PAGE.encode("utf-8"), "https://www.hasil.gov.my/en/ckht/kadar-cukai-keuntungan-harta-tanah/", "RPGT", "lhdn_content")
    assert len(entries) == 3 and all(e.valid_from is None and e.valid_until is None for e in entries)
    assert all(e.link == "https://www.hasil.gov.my/en/ckht/kadar-cukai-keuntungan-harta-tanah/" for e in entries)


_OL_PAGE = """<html><body><h1>Real Property Gains Tax (RPGT) Rates</h1>
<div class="elementor-widget elementor-widget-text-editor"><ol>
<li>RPGT rates differ according to disposer categories and holding period of chargeable asset, as per Schedule 5 RPGTA.</li>
<li>RPGT rate for a disposer under Part I Schedule 5 RPGTA:
<table><tr><td>Holding Period</td><td colspan="2">Disposal Date</td></tr>
<tr><td></td><td>1.1.2019 to 31.12.2021</td><td>Starting from the 1.1.2022</td></tr>
<tr><td>Within 2 years</td><td>30%</td><td>30%</td></tr>
<tr><td>In the 6th year and thereafter</td><td>5%</td><td>0%</td></tr></table></li>
</ol></div></body></html>"""


def test_a_table_inside_a_list_item_is_not_folded_into_its_caption() -> None:
    items = parse_lhdn_content(_OL_PAGE, "RPGT (LHDN)")
    titled = [i for i in items if "Part I Schedule 5" in i.title]
    assert len(titled) == 1
    # The caption is just the sentence, and the title carries no list dash.
    assert titled[0].title == "RPGT (LHDN) — RPGT rate for a disposer under Part I Schedule 5 RPGTA"
    first_line = titled[0].text.splitlines()[0]
    assert first_line.startswith("- RPGT rate for a disposer under Part I Schedule 5 RPGTA") and "30%" not in first_line
    assert any(line.endswith("Starting from the 1.1.2022: 30%") for line in titled[0].text.splitlines())


_YEARS_PAGE = """<html><body><nav>menu</nav>
<details><summary>Year of Assessment 2024</summary><table><tr><th>No.</th><th>Relief</th><th>Amount (RM)</th></tr>
<tr><td>14</td><td>Husband / wife</td><td>4,000</td></tr></table></details>
<details><summary>Year of Assessment 2025</summary><table><tr><th>No.</th><th>Relief</th><th>Amount (RM)</th></tr>
<tr><td>14</td><td>Husband / wife</td><td>4,000</td></tr></table></details>
<details><summary>How to claim</summary><p>Keep your receipts and claim the relief in the return form for the year.</p></details>
</body></html>"""


def test_only_current_year_items_are_kept_from_a_per_year_page() -> None:
    items = parse_lhdn_accordion_current(_YEARS_PAGE, "Individual Tax Reliefs (LHDN)")
    titles = [i.title for i in items]
    assert titles == [
        "Individual Tax Reliefs (LHDN) — Year of Assessment 2025",
        "Individual Tax Reliefs (LHDN) — How to claim",
    ]
    assert all(i.valid_until is None for i in items)  # the 2024 table (ended 31 Dec 2024) is not ingested


def test_the_current_extractor_fails_loudly_when_every_item_is_a_past_year() -> None:
    only_old = """<html><body><details><summary>Year of Assessment 2023</summary><p>old table text long enough to keep it</p></details>
<details><summary>Year of Assessment 2024</summary><p>old table text long enough to keep it too</p></details></body></html>"""
    # The newest year on the page stays current, so this page still yields its newest item.
    assert [i.title for i in parse_lhdn_accordion_current(only_old, "X")] == ["X — Year of Assessment 2024"]
    with pytest.raises(ExtractionError):
        parse_lhdn_accordion_current("<html><body><p>no accordion</p></body></html>", "X")


def test_the_two_per_year_sources_use_the_current_year_extractor() -> None:
    from scripts.sources import SOURCES_BY_NAME

    assert "lhdn_accordion_current" in EXTRACTORS
    for name in ("lhdn-tax-reliefs", "lhdn-individual-tax-rates"):
        assert SOURCES_BY_NAME[name].extractor == "lhdn_accordion_current"
