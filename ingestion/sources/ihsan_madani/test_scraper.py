"""Unit tests for the pure, network-free parts of scraper.py.

scrape_all/scrape_category (the network-fetching functions) are NOT
covered here — see scraper.py's module docstring on why. _parse_listing_page
IS tested below against a HAND-WRITTEN, PLAUSIBLE-BEST-GUESS Drupal 11
fixture — this confirms the parsing *logic* (fallback-selector order,
scope derivation, relative-URL resolution, fail-loud-on-missing-title)
works correctly against markup shaped like what Drupal 11 conventionally
emits. It is explicitly NOT proof the selectors match the REAL
ihsanmadani.gov.my markup — this sandbox has no egress to that site
(confirmed via direct curl: 403 at the proxy tunnel level), so nobody has
actually seen its real HTML yet. Whoever gets real network access must
still complete the TODO(verify-against-live-site) in scraper.py: fetch a
real page, diff its actual classes against _CARD_SELECTORS/_TITLE_SELECTORS/
_DESC_SELECTORS/_AGENCY_SELECTORS, and update the fixture below to match
reality (or add a second, real-markup-derived fixture alongside it).
"""
from __future__ import annotations

from .scraper import _parse_listing_page, parse_scope

# Plausible Drupal 11 "views-row" card markup — NOT sourced from the real
# site (see module docstring above). Exercises: the .views-row card
# selector, the title-link fallback chain, description/agency field
# extraction, relative-URL resolution for both aggregator_url and
# source_url, and the "Maklumat Lanjut" text-match link.
_FIXTURE_HTML = """
<html><body>
<div class="view-content">
  <div class="views-row">
    <h3><a href="/inisiatif/pendapatan/bantuan-sara-hidup">Bantuan Sara Hidup</a></h3>
    <div class="field--name-body">Bantuan tunai untuk isi rumah B40 berpendapatan rendah.</div>
    <div class="field--name-field-agency">Jabatan Kebajikan Masyarakat</div>
    <a href="/skim/bantuan-sara-hidup-maklumat">Maklumat Lanjut</a>
  </div>
  <div class="views-row">
    <h3><a href="/inisiatif/pendapatan/selangor-skim-tambahan">Selangor: Skim Tambahan Pendapatan</a></h3>
    <div class="field--name-body">Bantuan tambahan khas untuk penduduk Selangor.</div>
    <a href="https://example.gov.my/selangor-skim">Maklumat Lanjut</a>
  </div>
  <div class="views-row">
    <!-- no title link at all — must be skipped, not raise or fabricate -->
    <div class="field--name-body">Rekod tanpa tajuk.</div>
  </div>
</div>
</body></html>
"""


def test_parse_scope_state_prefix() -> None:
    assert parse_scope("Selangor: Skim Rawatan Jantung") == "state:selangor"


def test_parse_scope_case_insensitive() -> None:
    assert parse_scope("kuala lumpur: Bantuan Sewa") == "state:kuala-lumpur"


def test_parse_scope_no_prefix_defaults_federal() -> None:
    assert parse_scope("Bantuan Sara Hidup") == "federal"


def test_parse_scope_colon_without_state_defaults_federal() -> None:
    assert parse_scope("Program: Bantuan Am") == "federal"


def test_parse_scope_alias_penang() -> None:
    assert parse_scope("Penang: Skim X") == "state:pulau-pinang"


def test_parse_scope_alias_melaka_english() -> None:
    assert parse_scope("Malacca: Skim Y") == "state:melaka"


# ── _parse_listing_page against the synthetic fixture (see module docstring
# for why this is not a live-site verification) ─────────────────────────

def test_parse_listing_page_extracts_expected_field_count() -> None:
    records = _parse_listing_page(_FIXTURE_HTML, "pendapatan")
    assert len(records) == 2  # the title-less card is skipped, not fabricated


def test_parse_listing_page_resolves_relative_urls_against_base() -> None:
    records = _parse_listing_page(_FIXTURE_HTML, "pendapatan")
    first = records[0]
    assert first.aggregator_url == "https://ihsanmadani.gov.my/inisiatif/pendapatan/bantuan-sara-hidup"
    assert first.source_url == "https://ihsanmadani.gov.my/skim/bantuan-sara-hidup-maklumat"


def test_parse_listing_page_keeps_absolute_source_url_unchanged() -> None:
    records = _parse_listing_page(_FIXTURE_HTML, "pendapatan")
    second = records[1]
    assert second.source_url == "https://example.gov.my/selangor-skim"


def test_parse_listing_page_derives_scope_from_title_prefix() -> None:
    records = _parse_listing_page(_FIXTURE_HTML, "pendapatan")
    assert records[0].scope == "federal"
    assert records[1].scope == "state:selangor"


def test_parse_listing_page_falls_back_to_title_when_description_missing() -> None:
    """A card with a title but no description field must never produce a
    blank description — description defaults to the title text rather
    than an empty string (see MadaniScheme.description's min_length=1)."""
    html = """
    <div class="views-row">
      <h3><a href="/inisiatif/umum/no-desc-scheme">No Description Scheme</a></h3>
      <a href="/skim/no-desc">Maklumat Lanjut</a>
    </div>
    """
    records = _parse_listing_page(html, "umum")
    assert records[0].description == "No Description Scheme"


def test_parse_listing_page_missing_agency_is_none_not_fabricated() -> None:
    records = _parse_listing_page(_FIXTURE_HTML, "pendapatan")
    assert records[1].implementing_agency is None


def test_parse_listing_page_falls_back_to_aggregator_url_when_no_source_link() -> None:
    """Never leave source_url blank or invent one — fall back to the
    aggregator (listing-page) URL when no 'Maklumat Lanjut' link exists."""
    html = """
    <div class="views-row">
      <h3><a href="/inisiatif/umum/no-source-link">No Source Link Scheme</a></h3>
      <div class="field--name-body">Ada penerangan tetapi tiada pautan sumber.</div>
    </div>
    """
    records = _parse_listing_page(html, "umum")
    assert records[0].source_url == records[0].aggregator_url
    assert records[0].source_url == "https://ihsanmadani.gov.my/inisiatif/umum/no-source-link"
