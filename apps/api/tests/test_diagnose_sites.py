"""Tests for scripts.diagnose_sites: parsing and orchestration only, never the network."""
from __future__ import annotations

import ssl

import httpx
import pytest

from scripts import diagnose_sites as ds

_MOF_HTML = """
<html><body>
<table><tr><td onclick="window.open('/dokumen/surat-edaran-1.pdf')">SURAT EDARAN MOF PENGUATKUASAAN 2026</td></tr>
<tr><td data-file="/storage/pk-2-7.pdf">PK PINDAAN</td></tr></table>
<a href="#">dead</a><a href="javascript:void(0)">dead too</a><a href="/real">real</a>
<script>var u = "https://ppp.treasury.gov.my/files/garis-panduan.pdf";</script>
</body></html>
"""


def test_scan_raw_html_finds_addresses_hiding_outside_href() -> None:
    lines = "\n".join(ds.scan_raw_html(_MOF_HTML))
    assert "anchors with an empty, '#' or javascript: href: 2" in lines
    assert "document-looking URLs written in the raw HTML:" in lines and "/storage/pk-2-7.pdf" in lines
    assert "attribute td[onclick]: 1" in lines and "window.open('/dokumen/surat-edaran-1.pdf')" in lines
    assert "attribute td[data-file]: 1" in lines
    assert "row context:" in lines and "SURAT EDARAN MOF" in lines


def test_scan_raw_html_reports_nothing_found_plainly() -> None:
    lines = "\n".join(ds.scan_raw_html("<html><body><p>No documents here</p></body></html>"))
    assert "document-looking URLs written in the raw HTML: 0" in lines and "attribute" not in lines


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_check_mof_raw_reports_http_errors_and_transport_failures() -> None:
    assert ds.check_mof_raw(_client(lambda r: httpx.Response(403))) == ["HTTP 403"]

    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("slow")

    assert "ConnectTimeout" in ds.check_mof_raw(_client(boom))[0]


def test_sabah_retry_reports_every_attempt_on_both_hosts_and_pauses_between() -> None:
    seen: list[str] = []
    statuses = iter([500, 500, 200, 503, 503, 503])

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.host)
        return httpx.Response(next(statuses), headers={"server": "nginx"}, text="<h1>Internal Server Error</h1>")

    pauses: list[float] = []
    lines = ds.check_sabah(_client(handler), attempts=3, pause=4.0, sleep=pauses.append)
    assert len(lines) == 6 and seen == ["www.sabah.gov.my"] * 3 + ["sabah.gov.my"] * 3
    assert "HTTP 500" in lines[0] and "HTTP 200" in lines[2] and "Internal Server Error" in lines[0]
    assert pauses == [4.0] * 4  # between attempts, not after the last of each host


def test_moh_robots_prints_rules_when_served_and_the_block_when_not() -> None:
    ok = ds.check_moh_robots(_client(lambda r: httpx.Response(200, text="User-agent: *\nDisallow: /admin\n")))
    assert "HTTP 200" in ok[0] and "  Disallow: /admin" in ok
    blocked = ds.check_moh_robots(_client(lambda r: httpx.Response(403, text="<html>Access Denied</html>")))
    assert "HTTP 403" in blocked[0] and "Access Denied" in blocked[1]


def test_tls_variants_build_real_contexts_and_only_the_diagnostic_ones_skip_verification() -> None:
    variants = ds.tls_variants()
    assert len(variants) == 6
    for name, factory, _sni in variants:
        ctx = factory()
        assert isinstance(ctx, ssl.SSLContext)
        assert (ctx.verify_mode == ssl.CERT_NONE) == ("diagnostic only" in name), name
    assert ds.tls_variants()[1][1]().maximum_version == ssl.TLSVersion.TLSv1_2


def test_try_handshake_turns_any_failure_into_a_report_line() -> None:
    line = ds.try_handshake("127.0.0.1", "closed port", ssl.create_default_context, True)
    assert line.startswith("closed port: FAIL ")


def test_summarise_requests_lists_json_first() -> None:
    rows = ds.summarise_requests(
        [
            ("xhr", 200, "https://x.gov.my/b.html", "text/html"),
            ("fetch", 200, "https://x.gov.my/api/news", "application/json; charset=utf-8"),
        ]
    )
    assert rows[0].endswith("https://x.gov.my/api/news") and "application/json" in rows[0]


def test_render_page_degrades_when_playwright_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name.startswith("playwright"):
            raise ImportError("no playwright")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert "playwright is not installed" in ds.render_page("https://www.selangor.gov.my/")[0]


def test_run_check_rejects_unknown_names_and_main_survives_a_crashing_check(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(ValueError):
        ds.run_check("nope", httpx.Client())

    def crash(name: str, client: httpx.Client) -> list[str]:
        if name == "kpdn-tls":
            raise RuntimeError("boom")
        return [f"{name} fine"]

    monkeypatch.setattr(ds, "run_check", crash)
    assert ds.main(["--only", "kpdn-tls", "--only", "moh-robots"]) == 0
    out = capsys.readouterr().out
    assert "check crashed: RuntimeError: boom" in out and "moh-robots fine" in out
