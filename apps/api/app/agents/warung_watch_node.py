"""warung_watch_node — short-circuit answer for live "is X packed right
now" queries, bypassing rag/analyst/synthesiser entirely.

Runs only when router_node set is_live_status_query=True + a place_name —
see graph.py's conditional edge after router. This is live, crowdsourced
data with its own freshness/report-count framing, not a RAG citation, so
it deliberately does not go through analyst_node's confidence gate or
synthesiser_node's citation-chip formatting; it builds its own honest,
bilingual answer directly from core.warung_watch's aggregation output.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

import structlog
import weave
from langgraph.config import get_stream_writer
from supabase import AsyncClient, acreate_client

from app.models.state import AgentState
from core.warung_watch import STALE_WINDOW, aggregate_checkin_status, select_best_match

log = structlog.get_logger(__name__)

_STATUS_LABEL = {
    "bm": {"empty": "lengang", "moderate": "sederhana sibuk", "packed": "penuh sesak"},
    "en": {"empty": "quiet", "moderate": "moderately busy", "packed": "packed"},
    "zh": {"empty": "空闲", "moderate": "中等繁忙", "packed": "非常拥挤"},
}


async def _get_client() -> AsyncClient | None:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        return None
    return await acreate_client(url, key)


def _no_data_message(place_name: str, language: str) -> str:
    if language == "bm":
        return (
            f"Tiada laporan status terkini untuk \"{place_name}\" setakat ini. "
            "Warung Watch bergantung pada laporan orang ramai — jadilah yang pertama melapor!"
        )
    if language == "zh":
        return f'目前没有关于"{place_name}"的最新状态报告。Warung Watch 依赖网友的实时通报——欢迎成为第一位报告者！'
    return (
        f'No recent status reports for "{place_name}" yet. '
        "Warung Watch runs on crowdsourced check-ins — be the first to report!"
    )


def _format_answer(place_name: str, status_data: dict, language: str) -> str:
    status = status_data["status"]
    if status is None:
        return _no_data_message(place_name, language)

    label = _STATUS_LABEL.get(language, _STATUS_LABEL["en"])[status]
    count = status_data["report_count"]
    freshness_note = ""
    if not status_data["is_fresh"]:
        if language == "bm":
            freshness_note = " (laporan lebih lama daripada 2 jam — mungkin sudah tidak tepat)"
        elif language == "zh":
            freshness_note = "（报告超过2小时——可能已不准确）"
        else:
            freshness_note = " (reports are more than 2 hours old — may be out of date)"

    if language == "bm":
        return (
            f"{place_name} dilaporkan **{label}** sekarang{freshness_note}, "
            f"berdasarkan {count} laporan daripada orang ramai."
        )
    if language == "zh":
        return f"根据 {count} 位网友的通报，{place_name} 目前**{label}**{freshness_note}。"
    return (
        f"{place_name} is reported **{label}** right now{freshness_note}, "
        f"based on {count} crowd report{'s' if count != 1 else ''}."
    )


@weave.op()
async def warung_watch_node(state: AgentState) -> dict:
    place_name = state.get("place_name")
    language = state.get("language", "en")
    # Every return path must stream the answer via get_stream_writer(),
    # matching synthesiser_node/guard_node — the SSE endpoint's `custom`
    # stream mode is the ONLY thing that reaches the client as `token`
    # events (query.py only replays streaming_token_buffer for the
    # needs_clarification path, which this node never sets). Writing the
    # buffer alone, without also calling write(), silently drops the
    # answer text: the client gets metadata + done with no visible reply.
    write = get_stream_writer()

    def _respond(text: str) -> dict:
        write(text)
        return {"streaming_token_buffer": text, "citations": []}

    if not place_name:
        # Shouldn't happen — router_node already clears is_live_status_query
        # when place_name is missing — but never crash the turn on a
        # malformed state.
        return _respond(_no_data_message("that place", language))

    client = await _get_client()
    if client is None:
        log.warning("warung_watch_node_no_supabase_client")
        return _respond(_no_data_message(place_name, language))

    try:
        # Fetch a candidate pool and rank client-side (select_best_match) —
        # a bare `ilike(...).limit(1)` with no ordering would resolve
        # "pelita" to an arbitrary row among "pelita"/"restoran pelita"/etc.
        warung_res = (
            await client.table("warungs")
            .select("id,name")
            .ilike("normalized_name", f"%{place_name.strip().lower()}%")
            .limit(25)
            .execute()
        )
        warung = select_best_match(place_name, warung_res.data or [])
        if not warung:
            return _respond(_no_data_message(place_name, language))

        # Same STALE_WINDOW (24h) the REST /warung-watch/status endpoint
        # applies via get_status() — without this filter, chat could report
        # crowd status from reports far older than what a direct status
        # check would even surface.
        stale_cutoff = (datetime.now(timezone.utc) - STALE_WINDOW).isoformat()
        checkin_res = (
            await client.table("warung_checkins")
            .select("status,source,created_at")
            .eq("warung_id", warung["id"])
            .gte("created_at", stale_cutoff)
            .order("created_at", desc=True)
            .limit(50)
            .execute()
        )
        status_data = aggregate_checkin_status(checkin_res.data or [])
        answer = _format_answer(warung["name"], status_data, language)
        return _respond(answer)
    except Exception as exc:
        log.warning("warung_watch_node_error", error=str(exc), place_name=place_name)
        return _respond(_no_data_message(place_name, language))
