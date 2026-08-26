"""parliament_query_node — short-circuit answer for structured Parliament
lookups (a specific bill's vote record, or a specific MP/constituency),
bypassing rag/analyst/synthesiser entirely.

Runs only when router_node set is_structured_parliament_query=True with a
parliament_bill_number or parliament_mp_query — see graph.py's conditional
edge after guard. This reads directly from the existing structured tables
(mp_profiles / mp_votes / parliament_bills, FK-linked since migration
025_parliament_watch.sql — the "lightweight property graph as Postgres
tables" this domain needs) via services/parliament.py, the same functions
routers/parliament.py's REST endpoints already call. It is deliberately
NOT routed through rag_node: "which MPs voted against bill X" is a direct
relational read, not a chunk-retrieval-shaped question, and forcing it
through hybrid search would answer worse than a plain SQL join.

General Hansard debate-content questions ("what did parliament debate
about tax reform") are NOT structured lookups — router_node leaves
is_structured_parliament_query=False for those and they take the normal
RAG path (domain='parliament' content ingested by ingest_parliament/,
migration 026), unaffected by this node.
"""
from __future__ import annotations

import structlog
import weave
from langgraph.config import get_stream_writer
from supabase import create_client

from app.models.state import AgentState, Citation
from core.config import settings
from services.parliament import get_bill_vote_summary, search_mps

log = structlog.get_logger(__name__)

_PARLIMEN_FALLBACK_URL = "https://www.parlimen.gov.my"

_NO_BILL_MATCH = {
    "bm": 'Tiada rekod pengundian dijumpai untuk rang undang-undang "{q}".',
    "zh": '未找到法案"{q}"的投票记录。',
    "en": 'No vote records found for bill "{q}".',
}
_NO_MP_MATCH = {
    "bm": 'Tiada rekod Ahli Parlimen dijumpai untuk "{q}".',
    "zh": '未找到与"{q}"匹配的国会议员记录。',
    "en": 'No MP records found matching "{q}".',
}
_NO_DATA_CONFIGURED = {
    "bm": "Data Parlimen tidak tersedia buat masa ini.",
    "zh": "国会数据目前无法使用。",
    "en": "Parliament data is temporarily unavailable.",
}


def _get_client():
    if not settings.supabase_url or not settings.supabase_service_key:
        return None
    return create_client(settings.supabase_url, settings.supabase_service_key)


def _format_bill_answer(bill_number: str, summary: list[dict], language: str) -> str:
    parts = []
    for row in summary:
        vote = row.get("vote", "?")
        count = row.get("vote_count", 0)
        parts.append(f"{vote}: {count}")
    breakdown = ", ".join(parts)
    if language == "bm":
        return f'Rekod pengundian untuk "{bill_number}": {breakdown}.'
    if language == "zh":
        return f'"{bill_number}" 的投票记录：{breakdown}。'
    return f'Vote record for "{bill_number}": {breakdown}.'


def _format_mp_answer(mp: dict, language: str) -> str:
    name = mp.get("full_name", "?")
    party = mp.get("party") or "-"
    constituency = mp.get("constituency_name") or "-"
    if language == "bm":
        return f"{name} ({party}) ialah Ahli Parlimen bagi {constituency}."
    if language == "zh":
        return f"{name}（{party}）是{constituency}的国会议员。"
    return f"{name} ({party}) is the MP for {constituency}."


@weave.op()
async def parliament_query_node(state: AgentState) -> dict:
    language = state.get("language", "en")
    bill_number = state.get("parliament_bill_number")
    mp_query = state.get("parliament_mp_query")

    # Every return path streams via get_stream_writer(), matching
    # warung_watch_node/synthesiser_node — the SSE endpoint's `custom`
    # stream mode is the only thing that reaches the client as `token`
    # events; writing streaming_token_buffer alone silently drops the
    # answer text.
    write = get_stream_writer()

    def _respond(text: str, citations: list[Citation]) -> dict:
        write(text)
        return {"streaming_token_buffer": text, "citations": citations}

    if not bill_number and not mp_query:
        # Shouldn't happen — router_node already clears
        # is_structured_parliament_query when neither field is usable —
        # but never crash the turn on a malformed state.
        return _respond(_NO_DATA_CONFIGURED.get(language, _NO_DATA_CONFIGURED["en"]), [])

    client = _get_client()
    if client is None:
        log.warning("parliament_query_node_no_supabase_client")
        return _respond(_NO_DATA_CONFIGURED.get(language, _NO_DATA_CONFIGURED["en"]), [])

    try:
        if bill_number:
            summary = await get_bill_vote_summary(client, bill_number)
            if not summary:
                msg = _NO_BILL_MATCH.get(language, _NO_BILL_MATCH["en"]).format(q=bill_number)
                return _respond(msg, [])
            answer = _format_bill_answer(bill_number, summary, language)
            citation: Citation = {
                "title": f"Parliament vote record: {bill_number}",
                "ministry": "Parlimen Malaysia",
                "url": _PARLIMEN_FALLBACK_URL,
                "confidence": 1.0,
                "stale_disclaimer": False,
            }
            return _respond(answer, [citation])

        results = await search_mps(client, mp_query, limit=1)
        if not results:
            msg = _NO_MP_MATCH.get(language, _NO_MP_MATCH["en"]).format(q=mp_query)
            return _respond(msg, [])
        mp = results[0]
        answer = _format_mp_answer(mp, language)
        citation = {
            "title": f"MP profile: {mp.get('full_name', mp_query)}",
            "ministry": "Parlimen Malaysia",
            "url": mp.get("parlimen_url") or _PARLIMEN_FALLBACK_URL,
            "confidence": 1.0,
            "stale_disclaimer": False,
        }
        return _respond(answer, [citation])
    except Exception as exc:
        log.warning(
            "parliament_query_node_error",
            error=str(exc),
            bill_number=bill_number,
            mp_query=mp_query,
        )
        return _respond(_NO_DATA_CONFIGURED.get(language, _NO_DATA_CONFIGURED["en"]), [])
