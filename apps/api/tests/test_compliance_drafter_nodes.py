"""Compliance Drafter: the report builder, the email step, and send_email.

Everything network-facing is mocked. These pin behaviour that was broken:
empty reports (wrong corpus domains), unescaped markup in the report HTML, and
an email failure that crashed the run after the PDF existed.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from pydantic import ValidationError

from app.agents.compliance_drafter import nodes
from app.agents.compliance_drafter.nodes import compile_node, notify_node, query_epf_node, query_tax_node
from app.agents.router_node import _VALID_DOMAINS
from app.agents.tools import send_email
from app.routers.agents import AgentContinueRequest, AgentStartRequest

# Obviously fake data throughout: no real businesses, rules or URLs.
_FINDING = {
    "domain": "tax",
    "summary": "Test rule summary for a fake business.",
    "source_title": "Test Source",
    "source_url": "https://www.example.gov.my/test",
    "similarity": 0.8,
}


# ── Domains ──────────────────────────────────────────────────────────────────

def test_every_section_searches_a_canonical_corpus_domain() -> None:
    """The map pointed at finance/government, where production holds no chunks,
    so every section of every report was empty."""
    assert nodes._DOMAIN_MAP == {"tax": "tax", "business": "business", "epf": "epf"}
    assert set(nodes._DOMAIN_MAP.values()) <= set(_VALID_DOMAINS)


@pytest.mark.asyncio
@pytest.mark.parametrize(("node", "domain"), [(query_tax_node, "tax"), (query_epf_node, "epf")])
async def test_query_nodes_search_their_own_domain(node, domain) -> None:
    search = AsyncMock(return_value=[_FINDING])
    with patch.object(nodes, "query_rag_findings", search):
        out = await node({"domains": ["tax", "business", "epf"], "business_type": "sole_proprietor", "language": "en"})
    assert search.await_args.args[1] == domain
    assert out[f"{domain}_findings"] == [_FINDING]


# ── Report HTML ──────────────────────────────────────────────────────────────

async def _html(**state) -> str:
    out = await compile_node({"language": "en", "business_type": "sole_proprietor", **state})
    return out["report_html"]


@pytest.mark.asyncio
async def test_user_and_document_text_is_escaped_in_the_report() -> None:
    """business_type is user input; titles and summaries come from ingested
    documents. The HTML is rendered to PDF server-side, so none of it may stay markup."""
    evil = {**_FINDING, "source_title": "<img src=x onerror=alert(1)>", "summary": "<script>steal()</script>"}
    html = await _html(business_type="<script>alert(1)</script>", tax_findings=[evil])

    assert "<script>" not in html and "<img src=x" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


@pytest.mark.asyncio
async def test_only_real_web_urls_become_links() -> None:
    f = lambda url: {**_FINDING, "source_url": url}  # noqa: E731
    assert "<a href='https://www.example.gov.my/test'>" in await _html(tax_findings=[f("https://www.example.gov.my/test")])
    for bad in ("javascript:alert(1)", "file:///etc/passwd", "", "   "):
        assert "<a href" not in await _html(tax_findings=[f(bad)]), bad


@pytest.mark.asyncio
async def test_a_quote_in_a_url_cannot_break_out_of_the_attribute() -> None:
    html = await _html(tax_findings=[{**_FINDING, "source_url": "https://x.example/a'onmouseover='alert(1)"}])
    assert "'onmouseover=" not in html


@pytest.mark.asyncio
@pytest.mark.parametrize("language", ["bm", "en", "zh"])
async def test_an_empty_section_says_so_instead_of_showing_a_bare_heading(language) -> None:
    """A heading with nothing under it reads as 'no obligations here'."""
    html = await _html(language=language, tax_findings=[_FINDING], business_findings=[], epf_findings=[])

    assert "<ul></ul>" not in html
    assert nodes._NO_SOURCES[language] in html
    assert html.count(nodes._NO_SOURCES[language]) == 2  # business and epf; tax has a finding


@pytest.mark.asyncio
async def test_sections_the_user_did_not_request_are_left_out() -> None:
    """Asking for tax only must not produce 'no official source found' for
    business and EPF, which were never searched."""
    out = await compile_node({
        "language": "en", "business_type": "sole_proprietor", "domains": ["tax"], "tax_findings": [_FINDING],
    })

    assert [sec["title"] for sec in out["report_sections"]] == ["Tax (LHDN)"]
    assert "Business (SSM)" not in out["report_html"] and "EPF/KWSP" not in out["report_html"]
    assert nodes._NO_SOURCES["en"] not in out["report_html"]


@pytest.mark.asyncio
async def test_a_requested_section_with_no_findings_still_says_so() -> None:
    out = await compile_node({"language": "en", "domains": ["tax", "epf"], "tax_findings": [_FINDING], "epf_findings": []})

    assert [sec["title"] for sec in out["report_sections"]] == ["Tax (LHDN)", "EPF/KWSP"]
    assert out["report_html"].count(nodes._NO_SOURCES["en"]) == 1


@pytest.mark.asyncio
async def test_no_domains_given_means_all_three_sections() -> None:
    out = await compile_node({"language": "en"})  # intake_node's default
    assert len(out["report_sections"]) == 3


# ── Notification email ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_notify_escapes_the_signed_url_in_the_email() -> None:
    sent = AsyncMock(return_value=True)
    with patch("app.agents.tools.send_email", sent):
        out = await notify_node({"_user_email": "user@example.invalid", "signed_url": "https://s.example/x?a=1&b='2"})

    body = sent.await_args.kwargs["html_body"]
    assert "&amp;b=" in body and "'2" not in body.split("href='")[1].split("'>")[0]
    assert out["email_sent"] is True


@pytest.mark.asyncio
async def test_notify_does_not_email_without_a_download_link() -> None:
    sent = AsyncMock(return_value=True)
    with patch("app.agents.tools.send_email", sent):
        out = await notify_node({"_user_email": "user@example.invalid", "signed_url": ""})
    sent.assert_not_awaited()
    assert out["email_sent"] is False


# ── send_email ───────────────────────────────────────────────────────────────

def _client(post) -> MagicMock:
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=MagicMock(post=post))
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setattr("app.agents.tools.settings", MagicMock(resend_api_key="test-key", resend_from_email="a@example.invalid"))


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [httpx.ConnectError("down"), httpx.ReadTimeout("slow")])
async def test_send_email_survives_network_errors(configured, error) -> None:
    """A timeout used to propagate, failing the whole confirm call after the PDF
    existed and skipping the record of it."""
    with patch("app.agents.tools.httpx.AsyncClient", return_value=_client(AsyncMock(side_effect=error))):
        assert await send_email(to="user@example.invalid", subject="s", html_body="b") is False


@pytest.mark.asyncio
async def test_send_email_reports_provider_errors_and_success(configured) -> None:
    for status, expected in ((500, False), (422, False), (200, True)):
        post = AsyncMock(return_value=MagicMock(status_code=status))
        with patch("app.agents.tools.httpx.AsyncClient", return_value=_client(post)):
            assert await send_email(to="user@example.invalid", subject="s", html_body="b") is expected


@pytest.mark.asyncio
async def test_send_email_is_skipped_when_not_configured(monkeypatch) -> None:
    monkeypatch.setattr("app.agents.tools.settings", MagicMock(resend_api_key="  ", resend_from_email=""))
    assert await send_email(to="user@example.invalid", subject="s", html_body="b") is False


# ── Request bounds ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("model", [AgentStartRequest, AgentContinueRequest])
@pytest.mark.parametrize(
    "field", [("context", "x" * 5001), ("business_type", "x" * 101), ("domains", ["tax"] * 11)]
)
def test_compliance_inputs_are_bounded(model, field) -> None:
    extra = {"session_id": "s"} if model is AgentContinueRequest else {}
    name, value = field
    with pytest.raises(ValidationError):
        model(**extra, **{name: value})


def test_normal_inputs_are_accepted() -> None:
    req = AgentStartRequest(context="x" * 5000, business_type="sdn_bhd", domains=["tax", "epf"])
    assert req.business_type == "sdn_bhd"
