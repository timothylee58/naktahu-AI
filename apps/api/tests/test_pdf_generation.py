"""PDF generation: real rendering, honest failure, and no remote fetching.

Regression context: generate_pdf used to fall back to uploading raw HTML bytes
as application/pdf whenever WeasyPrint was missing (it was never a declared
dependency), so users were handed a file that was not a PDF and the email said
"Download PDF". These tests pin the replacement behaviour: a real PDF or an
empty result, never a fake one, and nothing is uploaded on failure.
"""
from __future__ import annotations

import base64
import http.server
import importlib
import socketserver
import sys
import threading
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.agents import tools
from app.agents.compliance_drafter.nodes import generate_pdf_node, notify_node
from app.agents.tools import (
    PDF_GENERATION_ERROR,
    PdfGenerationError,
    _RefuseAllFetcher,
    generate_pdf,
)
from app.routers import agents as agents_router
from core.config import settings
from services.agent_registry import load_agent_registry


def _weasyprint_unavailable_reason() -> str | None:
    """ImportError = package missing; OSError = package present but its native
    libraries (pango, harfbuzz, fontconfig) are not."""
    try:
        importlib.import_module("weasyprint")
    except (ImportError, OSError) as exc:
        return f"weasyprint cannot be imported here ({type(exc).__name__}: {exc})"
    return None


_SKIP_REASON = _weasyprint_unavailable_reason()
needs_weasyprint = pytest.mark.skipif(
    _SKIP_REASON is not None, reason=_SKIP_REASON or "weasyprint available"
)

_REPORT_HTML = (
    "<html><head><meta charset='utf-8'><title>Report</title></head>"
    "<body><h1>Compliance Report</h1><p>Test paragraph.</p></body></html>"
)

# 1x1 PNG, used to prove whether an image was actually fetched and embedded.
_PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def _mock_supabase(signed: dict[str, str] | None = None) -> MagicMock:
    sb = MagicMock()
    bucket = sb.storage.from_.return_value
    bucket.create_signed_url.return_value = (
        signed if signed is not None else {"signedURL": "https://signed.example/report.pdf"}
    )
    return sb


def _upload_mock(sb: MagicMock) -> MagicMock:
    return sb.storage.from_.return_value.upload


# ── Real rendering ───────────────────────────────────────────────────────────


@needs_weasyprint
def test_real_render_produces_pdf_bytes() -> None:
    pdf = tools._render_pdf_bytes(_REPORT_HTML)
    assert isinstance(pdf, bytes)
    assert pdf.startswith(b"%PDF")


@needs_weasyprint
@pytest.mark.parametrize(
    "text",
    [
        "合规报告：企业注册、税务与公积金（EPF）义务。",
        "Laporan Pematuhan: pendaftaran SSM, cukai LHDN dan caruman KWSP.",
        "Compliance report: SSM registration, LHDN tax and EPF contributions.",
        "Campuran / Mixed: Cukai 税务 Tax — RM1,234.50",
    ],
    ids=["zh", "ms", "en", "mixed"],
)
def test_multilingual_text_renders_without_raising(text: str) -> None:
    pdf = tools._render_pdf_bytes(f"<html><body><h1>{text}</h1><p>{text}</p></body></html>")
    assert pdf.startswith(b"%PDF")


@needs_weasyprint
@pytest.mark.asyncio
async def test_generate_pdf_uploads_a_real_pdf() -> None:
    sb = _mock_supabase()
    path, url, expires = await generate_pdf(
        _REPORT_HTML, user_id="u1", agent_type="compliance-drafter", supabase_client=sb
    )

    assert path.startswith("agents/compliance-drafter/u1/") and path.endswith(".pdf")
    assert url == "https://signed.example/report.pdf"
    assert expires
    upload = _upload_mock(sb)
    upload.assert_called_once()
    args = upload.call_args.args
    assert args[0] == path
    assert args[1].startswith(b"%PDF")
    assert args[2]["content-type"] == "application/pdf"


# ── Honest failure: nothing uploaded, no URL ────────────────────────────────


async def _assert_fails_closed(sb: MagicMock) -> None:
    result = await generate_pdf(_REPORT_HTML, user_id="u1", supabase_client=sb)
    assert result == ("", "", "")
    _upload_mock(sb).assert_not_called()
    sb.storage.from_.return_value.create_signed_url.assert_not_called()


@pytest.mark.asyncio
async def test_weasyprint_not_installed_uploads_nothing() -> None:
    sb = _mock_supabase()
    # A None entry in sys.modules makes `import weasyprint` raise ImportError,
    # whether or not the package is installed here.
    with patch.dict(sys.modules, {"weasyprint": None}):
        await _assert_fails_closed(sb)


@pytest.mark.asyncio
async def test_missing_native_libraries_uploads_nothing() -> None:
    """WeasyPrint installed but pango/harfbuzz absent: raises OSError on import.
    This is exactly what python:3.11-slim does without the apt packages."""
    sb = _mock_supabase()
    with patch.object(tools, "_render_pdf_bytes", side_effect=OSError("cannot load library 'libpango-1.0-0'")):
        await _assert_fails_closed(sb)


@pytest.mark.asyncio
async def test_render_exception_uploads_nothing() -> None:
    sb = _mock_supabase()
    with patch.object(tools, "_render_pdf_bytes", side_effect=RuntimeError("layout exploded")):
        await _assert_fails_closed(sb)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bad_output",
    [_REPORT_HTML.encode("utf-8"), b"", b"  %PDF-1.7 (leading whitespace)", "%PDF-1.7 (str, not bytes)"],
    ids=["html-bytes", "empty", "not-at-start", "str"],
)
async def test_non_pdf_output_uploads_nothing(bad_output: Any) -> None:
    sb = _mock_supabase()
    with patch.object(tools, "_render_pdf_bytes", return_value=bad_output):
        await _assert_fails_closed(sb)


@pytest.mark.asyncio
async def test_no_storage_client_returns_empty() -> None:
    with patch.object(tools, "_render_pdf_bytes", return_value=b"%PDF-1.7 fake"):
        assert await generate_pdf(_REPORT_HTML, user_id="u1", supabase_client=None) == ("", "", "")


@pytest.mark.asyncio
async def test_upload_failure_returns_empty() -> None:
    sb = _mock_supabase()
    _upload_mock(sb).side_effect = RuntimeError("storage down")
    with patch.object(tools, "_render_pdf_bytes", return_value=b"%PDF-1.7 fake"):
        assert await generate_pdf(_REPORT_HTML, user_id="u1", supabase_client=sb) == ("", "", "")


@pytest.mark.asyncio
async def test_missing_signed_url_returns_empty() -> None:
    sb = _mock_supabase(signed={})
    with patch.object(tools, "_render_pdf_bytes", return_value=b"%PDF-1.7 fake"):
        assert await generate_pdf(_REPORT_HTML, user_id="u1", supabase_client=sb) == ("", "", "")


@pytest.mark.asyncio
async def test_failure_is_logged_as_an_error() -> None:
    sb = _mock_supabase()
    with (
        patch.object(tools, "_render_pdf_bytes", side_effect=OSError("no pango")),
        patch.object(tools, "log") as log,
    ):
        await generate_pdf(_REPORT_HTML, user_id="u1", supabase_client=sb)
    log.error.assert_called_once()
    assert log.error.call_args.args[0] == "pdf_weasyprint_unavailable"


# ── No remote or local fetching while rendering ─────────────────────────────


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/hostname",
        "http://127.0.0.1:9/x.png",
        "https://example.invalid/x.css",
        "http://169.254.169.254/latest/meta-data/",
        "ftp://example.invalid/x",
        "data:image/png;base64,AAAA",
        "relative/path.png",
    ],
)
def test_url_fetcher_refuses_every_url(url: str) -> None:
    with pytest.raises(ValueError):
        _RefuseAllFetcher()(url)


def test_url_fetcher_never_fails_the_whole_render() -> None:
    """WeasyPrint >= 68 consults this attribute when a fetch raises; False means
    'skip the resource', True would abort the render."""
    assert _RefuseAllFetcher._fail_on_errors is False


@needs_weasyprint
def test_render_does_not_embed_local_files(tmp_path: Path) -> None:
    image = tmp_path / "secret.png"
    image.write_bytes(_PNG_1X1)
    html = f"<html><body><p>x</p><img src='{image.as_uri()}'></body></html>"

    # Control: WeasyPrint's default fetcher would read the local file, so the
    # assertion below is only meaningful because the same markup embeds it here.
    import weasyprint

    control = weasyprint.HTML(string=html).write_pdf()
    assert b"/Subtype /Image" in control

    rendered = tools._render_pdf_bytes(html)
    assert rendered.startswith(b"%PDF")
    assert b"/Subtype /Image" not in rendered


@needs_weasyprint
def test_render_makes_no_http_requests() -> None:
    hits: list[str] = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - http.server API
            hits.append(self.path)
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.end_headers()
            self.wfile.write(_PNG_1X1)

        def log_message(self, *args: Any) -> None:
            return

    with socketserver.TCPServer(("127.0.0.1", 0), Handler) as server:
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            html = (
                "<html><head><link rel='stylesheet' href='http://127.0.0.1:%d/a.css'></head>"
                "<body><img src='http://127.0.0.1:%d/b.png'>"
                "<p style=\"background:url('http://127.0.0.1:%d/c.png')\">x</p></body></html>"
            ) % (port, port, port)
            rendered = tools._render_pdf_bytes(html)
        finally:
            server.shutdown()
            thread.join(timeout=5)

    assert rendered.startswith(b"%PDF")
    assert hits == []


# ── generate_pdf_node / notify_node ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_node_sets_error_when_pdf_generation_fails() -> None:
    with patch("app.agents.tools.generate_pdf", AsyncMock(return_value=("", "", ""))):
        out = await generate_pdf_node({"report_html": _REPORT_HTML, "user_id": "u1"}, None)

    assert out["error"] == PDF_GENERATION_ERROR
    assert out["awaiting_hitl"] is False
    assert out["signed_url"] == ""
    assert out["pdf_storage_path"] == ""
    assert out["url_expires_at"] is None


@pytest.mark.asyncio
async def test_node_fails_closed_end_to_end_without_weasyprint() -> None:
    """Through the real generate_pdf: no PDF library means no upload and an error."""
    sb = _mock_supabase()
    with (
        patch.dict(sys.modules, {"weasyprint": None}),
        patch("app.agents.compliance_drafter.nodes.supabase_from_config", return_value=sb),
    ):
        out = await generate_pdf_node({"report_html": _REPORT_HTML, "user_id": "u1"}, None)

    assert out["error"] == PDF_GENERATION_ERROR
    assert out["signed_url"] == ""
    _upload_mock(sb).assert_not_called()


@pytest.mark.asyncio
async def test_node_success_clears_error_and_returns_url() -> None:
    fake = AsyncMock(return_value=("agents/x/u1/1.pdf", "https://signed.example/1.pdf", "2030-01-01T00:00:00+00:00"))
    with patch("app.agents.tools.generate_pdf", fake):
        out = await generate_pdf_node({"report_html": _REPORT_HTML, "user_id": "u1"}, None)

    assert out["error"] is None
    assert out["signed_url"] == "https://signed.example/1.pdf"
    assert out["pdf_storage_path"] == "agents/x/u1/1.pdf"
    assert out["awaiting_hitl"] is False


@pytest.mark.asyncio
async def test_notify_sends_no_email_after_a_failed_pdf() -> None:
    with patch("app.agents.tools.generate_pdf", AsyncMock(return_value=("", "", ""))):
        failed = await generate_pdf_node({"report_html": _REPORT_HTML, "user_id": "u1"}, None)

    send = AsyncMock(return_value=True)
    with patch("app.agents.tools.send_email", send):
        out = await notify_node({"_user_email": "user@example.invalid", **failed})

    send.assert_not_awaited()
    assert out["email_sent"] is False


@pytest.mark.asyncio
async def test_grant_draft_node_sets_error_when_pdf_generation_fails() -> None:
    from app.agents.grant_draft_generator.nodes import generate_export_node

    with patch("app.agents.tools.generate_pdf", AsyncMock(return_value=("", "", ""))):
        out = await generate_export_node(
            {"report_html": _REPORT_HTML, "user_id": "u1", "export_format": "pdf"}, None  # type: ignore[typeddict-item]
        )

    assert out["error"] == PDF_GENERATION_ERROR
    assert out["awaiting_hitl"] is False
    assert out["signed_url"] == ""


# ── agent_runner / router surface the failure ────────────────────────────────


def _auth_header(plan: str = "free") -> dict[str, str]:
    token = jwt.encode(
        {"sub": "u1", "aud": settings.supabase_jwt_aud, "app_metadata": {"plan": plan}},
        settings.jwt_secret,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def _client(supabase: object | None) -> TestClient:
    app = FastAPI()
    app.include_router(agents_router.router)
    from langgraph.checkpoint.memory import MemorySaver

    app.state.checkpointer = MemorySaver()
    app.state.supabase = supabase
    load_agent_registry(None)
    return TestClient(app)


@pytest.mark.asyncio
async def test_confirm_reports_error_and_does_not_persist_a_document() -> None:
    from app.services import agent_runner

    values = {"session_id": "s1", "error": PDF_GENERATION_ERROR, "signed_url": "", "pdf_storage_path": ""}
    sb = MagicMock()
    with (
        patch.object(agent_runner, "get_compliance_drafter_graph", return_value=MagicMock(aupdate_state=AsyncMock(), aget_state=AsyncMock(return_value=None))),
        patch.object(agent_runner, "_run_graph", AsyncMock(return_value=(values, ()))),
        patch.object(agent_runner, "_log_run") as log_run,
        patch.object(agent_runner, "_persist_document") as persist,
    ):
        resp = await agent_runner.confirm_compliance_drafter(
            session_id="s1", user_id="u1", user_email=None, supabase_client=sb, checkpointer=None
        )

    assert resp["status"] == "error"
    assert resp["error"] == PDF_GENERATION_ERROR
    assert not resp["signed_url"]
    assert log_run.call_args.args[-1] == "error"
    persist.assert_not_called()


def test_confirm_endpoint_does_not_charge_a_credit_when_pdf_failed() -> None:
    handler = AsyncMock(return_value={"session_id": "s1", "status": "error", "error": PDF_GENERATION_ERROR, "signed_url": ""})
    deduct = AsyncMock(return_value=4)
    with (
        patch.dict(agents_router.AGENT_CONFIRM_HANDLERS, {"compliance-drafter": handler}),
        patch.object(agents_router, "get_credits_remaining", AsyncMock(return_value=5)),
        patch.object(agents_router, "deduct_credits", deduct),
    ):
        res = _client(MagicMock()).post(
            "/api/v1/agents/compliance-drafter/confirm", json={"session_id": "s1"}, headers=_auth_header()
        )

    assert res.status_code == 200, res.text
    assert res.json()["error"] == PDF_GENERATION_ERROR
    deduct.assert_not_awaited()


def test_confirm_endpoint_still_charges_a_credit_on_success() -> None:
    handler = AsyncMock(return_value={"session_id": "s1", "status": "completed", "signed_url": "https://signed.example/1.pdf"})
    deduct = AsyncMock(return_value=4)
    with (
        patch.dict(agents_router.AGENT_CONFIRM_HANDLERS, {"compliance-drafter": handler}),
        patch.object(agents_router, "get_credits_remaining", AsyncMock(return_value=5)),
        patch.object(agents_router, "deduct_credits", deduct),
    ):
        res = _client(MagicMock()).post(
            "/api/v1/agents/compliance-drafter/confirm", json={"session_id": "s1"}, headers=_auth_header()
        )

    assert res.status_code == 200, res.text
    deduct.assert_awaited_once()


@pytest.mark.asyncio
async def test_health_triage_export_raises_when_pdf_generation_fails() -> None:
    from app.services.agent_runner import export_health_triage

    snapshot = MagicMock()
    snapshot.values = {"session_id": "h1", "user_id": "u1", "facility_recommendation": "Klinik Kesihatan."}
    graph = MagicMock()
    graph.aget_state = AsyncMock(return_value=snapshot)
    sb = MagicMock()
    with (
        patch("app.services.agent_runner.get_health_triage_graph", return_value=graph),
        patch("app.agents.tools.generate_pdf", AsyncMock(return_value=("", "", ""))),
    ):
        with pytest.raises(PdfGenerationError):
            await export_health_triage(session_id="h1", checkpointer=None, supabase_client=sb, user_id="u1")

    sb.table.assert_not_called()


def test_health_triage_export_endpoint_503_when_pdf_generation_fails() -> None:
    with patch.object(agents_router, "export_health_triage", AsyncMock(side_effect=PdfGenerationError("x"))):
        res = _client(MagicMock()).post("/api/v1/agents/health-triage/h1/export", headers=_auth_header())
    assert res.status_code == 503
