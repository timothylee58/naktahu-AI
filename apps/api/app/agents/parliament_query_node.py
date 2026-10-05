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

import re

import structlog
import weave
from langgraph.config import get_stream_writer
from supabase import create_client

from app.models.state import AgentState, Citation
from core.config import settings
from services.parliament import get_bill_vote_summary, get_mps_by_postcode, search_mps

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
_NEED_POSTCODE = {
    "bm": "Saya boleh cari Ahli Parlimen anda melalui poskod. Tanya semula dengan poskod anda, contohnya: \"Siapa Ahli Parlimen saya untuk 50450?\"",
    "zh": "我可以根据邮政编码查找您的国会议员。请附上您的邮政编码再问一次，例如：\"50450 的国会议员是谁？\"",
    "en": "I can find your MP from your postcode. Ask again with it, for example: \"Who is my MP for 50450?\"",
}
_NO_POSTCODE_MATCH = {
    "bm": "Saya belum dapat padankan poskod {postcode} dengan kawasan Parlimen. Cuba tanya dengan nama kawasan atau nama Ahli Parlimen.",
    "zh": "暂时无法将邮政编码 {postcode} 对应到国会选区。请改用选区名称或议员姓名询问。",
    "en": "I can't match postcode {postcode} to a parliamentary seat yet. Try asking with the constituency or MP's name instead.",
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


# "my MP", "my constituency", "kawasan saya", "我的选区" — a question about the
# asker's own seat, which no name search can answer. router_node passes the
# phrase through as parliament_mp_query ("my constituency"), and searching
# mp_profiles for that literal text is what produced "No MP records found
# matching 'my constituency'".
_SELF_REFERENCE_RE = re.compile(r"\b(?:my|our|mine|saya|aku|kami|kita)\b|我", re.IGNORECASE)
_POSTCODE_IN_TEXT_RE = re.compile(r"(?<!\d)(\d{5})(?!\d)")


def _postcode_for(query: str, mp_query: str, state_postcode: str | None) -> str | None:
    """A postcode stated in the question wins; else the one the client saved."""
    for text in (mp_query, query):
        m = _POSTCODE_IN_TEXT_RE.search(text or "")
        if m:
            return m.group(1)
    if state_postcode and re.fullmatch(r"\d{5}", state_postcode):
        return state_postcode
    return None


_LABELS = {
    "bm": {"seats": "Poskod {postcode} merentasi {n} kawasan Parlimen:", "office": "Pejabat", "no_office": "tiada maklumat pejabat dalam rekod lagi"},
    "zh": {"seats": "邮政编码 {postcode} 横跨 {n} 个国会选区：", "office": "办事处", "no_office": "暂无办事处联系资料"},
    "en": {"seats": "Postcode {postcode} spans {n} parliamentary seats:", "office": "Office", "no_office": "no office contact on record yet"},
}


def _format_postcode_answer(postcode: str, mps: list[dict], language: str) -> str:
    labels = _LABELS.get(language, _LABELS["en"])
    lines = [labels["seats"].format(postcode=postcode, n=len(mps))] if len(mps) > 1 else []
    for mp in mps:
        name = " ".join(p for p in (mp.get("salutation"), mp.get("full_name")) if p)
        seat = f"{mp.get('constituency_code', '')} {mp.get('constituency_name', '')}".strip()
        party = f" ({mp['party']})" if mp.get("party") else ""
        if language == "bm":
            head = f"{name}{party} ialah Ahli Parlimen bagi {seat}."
        elif language == "zh":
            head = f"{name}{party}是{seat}的国会议员。"
        else:
            head = f"{name}{party} is the MP for {seat}."
        contact = [c for c in (mp.get("office_address"), mp.get("office_phone"), mp.get("office_email")) if c]
        office = f"{labels['office']}: {' · '.join(contact)}" if contact else f"{labels['office']}: {labels['no_office']}."
        lines.append(f"{'- ' if len(mps) > 1 else ''}{head} {office}")
    return "\n".join(lines)


def _mp_citation(mp: dict) -> Citation:
    return {
        "title": f"MP profile: {mp.get('full_name', '')}",
        "ministry": "Parlimen Malaysia",
        "url": mp.get("parlimen_url") or _PARLIMEN_FALLBACK_URL,
        "confidence": 1.0,
        "stale_disclaimer": False,
    }


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

        postcode = _postcode_for(state.get("query", ""), mp_query, state.get("user_postcode"))
        is_own_seat = bool(_SELF_REFERENCE_RE.search(mp_query)) or bool(re.fullmatch(r"\s*\d{5}\s*", mp_query))
        if is_own_seat:
            if not postcode:
                return _respond(_NEED_POSTCODE.get(language, _NEED_POSTCODE["en"]), [])
            mps = await get_mps_by_postcode(client, postcode)
            if not mps:
                msg = _NO_POSTCODE_MATCH.get(language, _NO_POSTCODE_MATCH["en"]).format(postcode=postcode)
                return _respond(msg, [])
            return _respond(_format_postcode_answer(postcode, mps, language), [_mp_citation(mp) for mp in mps[:3]])

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
