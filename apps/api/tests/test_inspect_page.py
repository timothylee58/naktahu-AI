"""scripts/inspect_page.py: the report that tells main content from navigation."""
from __future__ import annotations

from bs4 import BeautifulSoup

from scripts.inspect_page import container_report, find_report, table_report

_PAGE = """
<html><head><title>Tax Rate</title></head><body>
<nav id="menu" class="mega">{menu}</nav>
<div id="content" class="entry"><h1>Tax Rate</h1>
<table><tr><th>Chargeable income</th><th>Rate</th></tr>
<tr><td>0 - 5,000</td><td>0%</td></tr><tr><td>5,001 - 20,000</td><td>1%</td></tr></table>
<p>{body}</p></div>
<footer>(c) 2026</footer></body></html>
""".format(menu="<a>Menu item words</a> " * 60, body="Resident individuals are taxed progressively. " * 12)


def _soup() -> BeautifulSoup:
    return BeautifulSoup(_PAGE, "html.parser")


def test_container_report_separates_a_digit_heavy_content_area_from_a_wordy_menu():
    lines = container_report(_soup())
    content = next(line for line in lines if "div#content.entry" in line)
    menu = next(line for line in lines if "nav#menu.mega" in line)
    assert " 1 tables" in content or " 1 tables  div#content" in content
    # The menu has no digits at all; the content area has the table's numbers.
    assert " 0 digits" in menu
    assert " 0 digits" not in content


def test_table_report_lists_rows_and_flags_digits():
    lines = table_report(_soup())
    assert any("table[0]" in l and "3 rows" in l for l in lines)
    assert any("0 - 5,000" in l and "0%" in l for l in lines)


def test_find_report_gives_the_ancestor_chain_of_a_phrase():
    lines = find_report(_soup(), ["5,001"])
    assert any("1 text node(s)" in l for l in lines)
    assert any("td" in l and "div#content.entry" in l for l in lines)


def test_find_report_says_when_a_phrase_is_absent():
    assert "0 text node(s)" in find_report(_soup(), ["no such phrase"])[0]


_ACCORDION = """
<div class="e-n-accordion">
 <details class="e-n-accordion-item"><summary class="e-n-accordion-item-title"><span>YA 2025</span></summary>
  <div><ul><li>Company with paid up capital not more than RM2.5 million
        <ul><li>First RM150,000 <strong>(15%)</strong></li><li>Next RM450,000 <strong>(17%)</strong></li></ul></li></ul></div></details>
 <details class="e-n-accordion-item"><summary>YA 2024</summary>
  <div><table><tr><th>Chargeable Income (RM)</th><th>Rate (%)</th></tr><tr><td>5,001 – 20,000</td><td>1</td></tr></table></div></details>
</div>
"""


def test_accordion_report_lists_items_with_titles_and_shape():
    from scripts.inspect_page import accordion_report

    lines = accordion_report(BeautifulSoup(_ACCORDION, "html.parser"))
    assert "2 top-level <details> item(s)" in lines[0]
    assert any("'YA 2025'" in l and "2 li" not in l and "3 li" in l for l in lines)
    assert any("'YA 2024'" in l and "1 tables" in l for l in lines)


def test_render_structured_keeps_list_nesting_and_table_rows():
    from scripts.inspect_page import render_structured

    soup = BeautifulSoup(_ACCORDION, "html.parser")
    for tag in soup.find_all("summary"):
        tag.extract()
    text = "\n".join(render_structured(soup))
    assert "- Company with paid up capital not more than RM2.5 million" in text
    assert "First RM150,000 (15%)" in text
    assert "Chargeable Income (RM) | Rate (%)" in text and "5,001 – 20,000 | 1" in text
