"""Follow-ups to the PDF and freshness work: honest .docx failure, PDF rendering
off the event loop, the Compliance Drafter relevance floor, and retrying a
failed PDF without re-running the searches."""
from __future__ import annotations

import sys
import threading
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents import tools
from app.agents.tools import PDF_GENERATION_ERROR, generate_docx
from app.services.vector_store import ChunkResult


def _sb(signed: dict[str, str] | None = None) -> MagicMock:
    sb = MagicMock()
    sb.storage.from_.return_value.create_signed_url.return_value = (
        {"signedURL": "https://signed.example/f"} if signed is None else signed
    )
    return sb


_REPORT = {"programme_name": "Grant", "executive_summary": "s", "use_of_funds_narrative": "u"}


# ── generate_docx fails closed ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_docx_uploads_a_real_word_document() -> None:
    sb = _sb()
    path, url, expires = await generate_docx(_REPORT, user_id="u1", supabase_client=sb)

    assert path.endswith(".docx") and url and expires
    uploaded = sb.storage.from_.return_value.upload.call_args.args[1]
    assert uploaded.startswith(b"PK")  # a .docx is a zip archive


@pytest.mark.asyncio
async def test_docx_library_missing_uploads_nothing() -> None:
    sb = _sb()
    # A None entry makes `from docx import Document` raise ImportError.
    with patch.dict(sys.modules, {"docx": None}):
        result = await generate_docx(_REPORT, user_id="u1", supabase_client=sb)

    assert result == ("", "", "")
    sb.storage.from_.return_value.upload.assert_not_called()


@pytest.mark.asyncio
async def test_docx_render_error_uploads_nothing() -> None:
    sb = _sb()
    fake_docx = MagicMock()
    fake_docx.Document.side_effect = RuntimeError("boom")
    with patch.dict(sys.modules, {"docx": fake_docx}):
        result = await generate_docx(_REPORT, user_id="u1", supabase_client=sb)

    assert result == ("", "", "")
    sb.storage.from_.return_value.upload.assert_not_called()


@pytest.mark.asyncio
async def test_docx_upload_failure_returns_empty() -> None:
    sb = _sb()
    sb.storage.from_.return_value.upload.side_effect = RuntimeError("storage down")
    assert await generate_docx(_REPORT, user_id="u1", supabase_client=sb) == ("", "", "")


@pytest.mark.asyncio
async def test_docx_missing_signed_url_returns_empty() -> None:
    assert await generate_docx(_REPORT, user_id="u1", supabase_client=_sb({})) == ("", "", "")


@pytest.mark.asyncio
async def test_grant_export_node_sets_error_when_docx_fails() -> None:
    from app.agents.grant_draft_generator import nodes

    state: dict[str, Any] = {"export_format": "docx", "report_json": _REPORT, "user_id": "u1"}
    with patch("app.agents.tools.generate_docx", AsyncMock(return_value=("", "", ""))):
        out = await nodes.generate_export_node(state, None)

    assert out["error"] == PDF_GENERATION_ERROR
    assert out["signed_url"] == "" and out["docx_storage_path"] == ""
    assert out["awaiting_hitl"] is False


# ── rendering does not block the event loop ───────────────────────────────────


@pytest.mark.asyncio
async def test_pdf_render_runs_in_a_worker_thread() -> None:
    seen: dict[str, int] = {}

    def fake_render(html: str) -> bytes:
        seen["thread"] = threading.get_ident()
        return b"%PDF-1.7 fake"

    with patch.object(tools, "_render_pdf_bytes", fake_render):
        path, url, _ = await tools.generate_pdf("<p>x</p>", user_id="u1", supabase_client=_sb())

    assert path and url
    assert seen["thread"] != threading.get_ident()


# ── relevance floor ───────────────────────────────────────────────────────────


def _chunk(cid: str, similarity: float) -> ChunkResult:
    return ChunkResult(
        id=cid,
        content=f"content {cid}",
        source_title=f"Source {cid}",
        source_url="https://www.example.gov.my/x",
        ministry="Ministry",
        language="en",
        similarity=similarity,
    )


@pytest.mark.asyncio
async def test_chunks_below_the_floor_are_dropped_and_counted() -> None:
    chunks = [_chunk("good", 0.55), _chunk("edge", 0.2), _chunk("junk", 0.08)]
    with patch.object(tools, "search_chunks", AsyncMock(return_value=chunks)):
        out = await tools.query_rag_freshness("q", "tax")

    assert [f["source_title"] for f in out["current"]] == ["Source good", "Source edge"]
    assert out["dropped"]["low_relevance"] == 1


@pytest.mark.asyncio
async def test_floor_can_be_disabled_by_setting_it_to_zero() -> None:
    chunks = [_chunk("junk", 0.01)]
    with (
        patch.object(tools, "search_chunks", AsyncMock(return_value=chunks)),
        patch.object(tools.settings, "drafter_min_relevance", 0.0),
    ):
        out = await tools.query_rag_freshness("q", "tax")

    assert len(out["current"]) == 1 and out["dropped"]["low_relevance"] == 0


@pytest.mark.asyncio
async def test_all_chunks_irrelevant_gives_an_empty_section_that_says_so() -> None:
    from app.agents.compliance_drafter import nodes

    with patch.object(tools, "search_chunks", AsyncMock(return_value=[_chunk("junk", 0.05)])):
        update = await nodes.query_tax_node(
            {"domains": ["tax"], "business_type": "x", "context": "", "language": "en"}  # type: ignore[typeddict-item]
        )
    assert update["tax_findings"] == []
    assert update["tool_calls"][-1]["low_relevance_dropped"] == 1

    state: dict[str, Any] = {"domains": ["tax"], "language": "en", "business_type": "x", **update}
    compiled = await nodes.compile_node(state)  # type: ignore[arg-type]
    assert "No official source was found" in compiled["report_html"]


def test_floor_is_bounded_in_config() -> None:
    from pydantic import ValidationError

    from core.config import Settings

    assert Settings(drafter_min_relevance=0.4).drafter_min_relevance == 0.4
    with pytest.raises(ValidationError):
        Settings(drafter_min_relevance=1.5)


# ── retrying a failed PDF ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_confirming_again_after_a_failed_pdf_retries_only_the_pdf_step() -> None:
    from langgraph.checkpoint.memory import MemorySaver

    from app.agents.compliance_drafter import nodes
    from app.services import agent_runner

    checkpointer = MemorySaver()
    empty = {"current": [], "announced": [], "dropped": {"superseded": 0, "expired": 0, "low_relevance": 0}}
    searches = {"n": 0}
    pdf_calls: list[str] = []

    async def fake_search(*_a: Any, **_k: Any) -> dict[str, Any]:
        searches["n"] += 1
        return empty

    async def flaky_pdf(html: str, **_k: Any) -> tuple[str, str, str]:
        pdf_calls.append(html)
        if len(pdf_calls) == 1:
            return "", "", ""
        return "agents/x/u1/1.pdf", "https://signed.example/r.pdf", "2030-01-01T00:00:00+00:00"

    with (
        patch.object(nodes, "query_rag_freshness", fake_search),
        patch("app.agents.tools.generate_pdf", flaky_pdf),
        patch("app.agents.tools.send_email", AsyncMock(return_value=True)),
    ):
        started = await agent_runner.start_compliance_drafter(
            user_id="u1", user_email="a@b.c", payload={"business_type": "x"}, supabase_client=None, checkpointer=checkpointer
        )
        sid = started["session_id"]
        searches_before_confirm = searches["n"]

        first = await agent_runner.confirm_compliance_drafter(
            session_id=sid, user_id="u1", user_email="a@b.c", supabase_client=None, checkpointer=checkpointer
        )
        second = await agent_runner.confirm_compliance_drafter(
            session_id=sid, user_id="u1", user_email="a@b.c", supabase_client=None, checkpointer=checkpointer
        )

    assert first["status"] == "error" and first["error"] == PDF_GENERATION_ERROR
    assert second["status"] == "completed" and not second.get("error")
    assert second["signed_url"] == "https://signed.example/r.pdf"
    assert second["email_sent"] is True
    assert len(pdf_calls) == 2
    # The report the user reviewed is reused: the searches are not run again.
    assert searches["n"] == searches_before_confirm
    assert pdf_calls[0] == pdf_calls[1]


@pytest.mark.asyncio
async def test_a_second_confirm_after_success_does_not_regenerate() -> None:
    from langgraph.checkpoint.memory import MemorySaver

    from app.agents.compliance_drafter import nodes
    from app.services import agent_runner

    checkpointer = MemorySaver()
    empty = {"current": [], "announced": [], "dropped": {"superseded": 0, "expired": 0, "low_relevance": 0}}
    pdf = AsyncMock(return_value=("p.pdf", "https://signed.example/r.pdf", "2030-01-01T00:00:00+00:00"))

    with (
        patch.object(nodes, "query_rag_freshness", AsyncMock(return_value=empty)),
        patch("app.agents.tools.generate_pdf", pdf),
        patch("app.agents.tools.send_email", AsyncMock(return_value=True)),
    ):
        started = await agent_runner.start_compliance_drafter(
            user_id="u1", user_email=None, payload={}, supabase_client=None, checkpointer=checkpointer
        )
        sid = started["session_id"]
        for _ in range(2):
            await agent_runner.confirm_compliance_drafter(
                session_id=sid, user_id="u1", user_email=None, supabase_client=None, checkpointer=checkpointer
            )

    assert pdf.await_count == 1


# ── the same retry for the Grant Draft Generator ──────────────────────────────


async def _grant_fetch(_state: Any, _config: Any = None) -> dict[str, Any]:
    return {"grant_record": {"programme_name": "SME Grant", "agency": "Agency"}}


async def _grant_draft(_state: Any) -> dict[str, Any]:
    return {"executive_summary": "summary", "use_of_funds_narrative": "funds", "document_checklist": []}


@pytest.mark.asyncio
@pytest.mark.parametrize("export_format", ["pdf", "docx"])
async def test_grant_confirm_again_after_a_failed_export_retries_only_the_export(export_format: str) -> None:
    from langgraph.checkpoint.memory import MemorySaver

    from app.agents.grant_draft_generator import graph as grant_graph
    from app.services import agent_runner

    checkpointer = MemorySaver()
    calls: list[str] = []

    async def flaky_export(*_a: Any, **_k: Any) -> tuple[str, str, str]:
        calls.append("export")
        if len(calls) == 1:
            return "", "", ""
        return "agents/g/u1/1.file", "https://signed.example/g", "2030-01-01T00:00:00+00:00"

    with (
        patch.object(grant_graph, "fetch_grant_node", _grant_fetch),
        patch.object(grant_graph, "draft_node", _grant_draft),
        patch("app.agents.tools.generate_pdf", flaky_export),
        patch("app.agents.tools.generate_docx", flaky_export),
        patch("app.agents.tools.send_email", AsyncMock(return_value=True)),
    ):
        started = await agent_runner.start_grant_draft_generator(
            user_id="u1",
            payload={"programme_name": "SME Grant", "export_format": export_format},
            supabase_client=None,
            checkpointer=checkpointer,
        )
        sid = started["session_id"]
        first = await agent_runner.confirm_grant_draft_generator(
            session_id=sid, user_id="u1", user_email="a@b.c", supabase_client=None, checkpointer=checkpointer
        )
        second = await agent_runner.confirm_grant_draft_generator(
            session_id=sid, user_id="u1", user_email="a@b.c", supabase_client=None, checkpointer=checkpointer
        )

    assert first["status"] == "error" and first["error"] == PDF_GENERATION_ERROR
    assert second["status"] == "completed" and not second.get("error")
    assert second["signed_url"] == "https://signed.example/g"
    assert len(calls) == 2
