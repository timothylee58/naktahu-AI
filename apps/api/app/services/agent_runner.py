"""Orchestrate product-agent graph runs, checkpoints, and audit logging."""
from __future__ import annotations

import time
import uuid
from typing import Any, Callable, Optional

import structlog

from langgraph.types import Command

from app.agents.compliance_drafter.graph import get_compliance_drafter_graph
from app.agents.compliance_drafter.state import ComplianceDrafterState
from app.agents.eligibility_agent.graph import get_eligibility_agent_graph
from app.agents.grant_draft_generator.graph import get_grant_draft_generator_graph
from app.agents.grant_draft_generator.state import GrantDraftState
from app.agents.health_triage.graph import get_health_triage_graph
from app.agents.immigration_navigator.graph import get_immigration_navigator_graph
from app.agents.research_synthesiser.graph import get_research_synthesiser_graph
from app.agents.retrenchment_navigator.graph import get_retrenchment_navigator_graph
from app.agents.sme_compliance_navigator.graph import get_sme_compliance_navigator_graph
from app.agents.study_agent.graph import get_study_agent_graph

log = structlog.get_logger(__name__)


def _thread_config(session_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": session_id}}


def _base_response(session_id: str, values: dict[str, Any], *, awaiting: tuple = ()) -> dict[str, Any]:
    status = values.get("status") or ("awaiting_hitl" if awaiting else "completed")
    return {
        "session_id": session_id,
        "status": status,
        "output": _public_output(values),
        "turns_count": values.get("turns_count", 1),
    }


def _public_output(values: dict[str, Any]) -> dict[str, Any]:
    skip = {"_supabase", "_user_email", "_rag_findings", "document_base64", "paper_text"}
    return {k: v for k, v in values.items() if not k.startswith("_") and k not in skip}


def _log_run(
    supabase_client: Any,
    user_id: str,
    agent_name: str,
    session_id: str,
    input_payload: dict[str, Any],
    output: dict[str, Any],
    latency_ms: int,
    status: str,
) -> None:
    if not supabase_client:
        return
    try:
        supabase_client.table("agent_runs").insert({
            "user_id": user_id,
            "agent_name": agent_name,
            "session_id": session_id,
            "input": input_payload,
            "output": _public_output(output),
            "turns_count": output.get("turns_count", 1),
            "tool_calls": output.get("tool_calls") or [],
            "completion_status": status,
            "latency_ms": latency_ms,
        }).execute()
    except Exception as exc:
        log.warning("agent_run_log_failed", error=str(exc))


async def _run_graph(
    graph,
    session_id: str,
    inputs: dict[str, Any],
    *,
    resume: bool = False,
) -> tuple[dict[str, Any], tuple]:
    t0 = time.monotonic()
    if resume:
        await graph.ainvoke(Command(resume=True), config=_thread_config(session_id))
    else:
        await graph.ainvoke(inputs, config=_thread_config(session_id))
    latency_ms = round((time.monotonic() - t0) * 1000)
    snapshot = await graph.aget_state(_thread_config(session_id))
    values = dict(snapshot.values) if snapshot else {}
    values["latency_ms"] = latency_ms
    awaiting = snapshot.next if snapshot else ()
    return values, awaiting


# ── Compliance Drafter ──────────────────────────────────────────────────────


async def start_compliance_drafter(
    *,
    user_id: str,
    user_email: Optional[str],
    payload: dict[str, Any],
    supabase_client: Any,
    checkpointer: Any,
) -> dict[str, Any]:
    session_id = str(uuid.uuid4())
    graph = get_compliance_drafter_graph(checkpointer=checkpointer)
    inputs: ComplianceDrafterState = {
        "session_id": session_id,
        "user_id": user_id,
        "business_type": payload.get("business_type", "sole_proprietor"),
        "domains": payload.get("domains") or ["tax", "business", "epf"],
        "context": payload.get("context", ""),
        "language": payload.get("language", "bm"),
        "turns_count": 0,
        "tool_calls": [],
        "_supabase": supabase_client,
        "_user_email": user_email,
    }
    values, awaiting = await _run_graph(graph, session_id, inputs)
    _log_run(supabase_client, user_id, "compliance-drafter", session_id, payload, values, values.get("latency_ms", 0), "awaiting_hitl" if awaiting else "completed")
    resp = _base_response(session_id, values, awaiting=awaiting)
    resp["awaiting_hitl"] = bool(awaiting)
    resp["report_json"] = values.get("report_json")
    return resp


async def continue_compliance_drafter(
    *,
    session_id: str,
    user_id: str,
    payload: dict[str, Any],
    checkpointer: Any,
) -> dict[str, Any]:
    graph = get_compliance_drafter_graph(checkpointer=checkpointer)
    update: dict[str, Any] = {}
    for key in ("context", "business_type", "domains"):
        if payload.get(key):
            update[key] = payload[key]
    if update:
        await graph.aupdate_state(_thread_config(session_id), update)
    t0 = time.monotonic()
    await graph.ainvoke(None, config=_thread_config(session_id))
    latency_ms = round((time.monotonic() - t0) * 1000)
    snapshot = await graph.aget_state(_thread_config(session_id))
    values = dict(snapshot.values) if snapshot else {}
    values["latency_ms"] = latency_ms
    awaiting = snapshot.next if snapshot else ()
    resp = _base_response(session_id, values, awaiting=awaiting)
    resp["report_json"] = values.get("report_json")
    return resp


async def confirm_compliance_drafter(
    *,
    session_id: str,
    user_id: str,
    user_email: Optional[str],
    supabase_client: Any,
    checkpointer: Any,
) -> dict[str, Any]:
    graph = get_compliance_drafter_graph(checkpointer=checkpointer)
    await graph.aupdate_state(_thread_config(session_id), {"_supabase": supabase_client, "_user_email": user_email})
    values, _ = await _run_graph(graph, session_id, {}, resume=True)
    _log_run(supabase_client, user_id, "compliance-drafter", session_id, {"confirm": True}, values, values.get("latency_ms", 0), "completed")
    if supabase_client and values.get("pdf_storage_path"):
        _persist_document(supabase_client, user_id, "compliance-drafter", values)
    resp = _base_response(session_id, values)
    resp["signed_url"] = values.get("signed_url")
    resp["url_expires_at"] = values.get("url_expires_at")
    resp["email_sent"] = values.get("email_sent", False)
    return resp


async def get_compliance_status(session_id: str, checkpointer: Any) -> dict[str, Any]:
    graph = get_compliance_drafter_graph(checkpointer=checkpointer)
    snapshot = await graph.aget_state(_thread_config(session_id))
    if not snapshot or not snapshot.values:
        return {"session_id": session_id, "status": "not_found"}
    values = dict(snapshot.values)
    awaiting = snapshot.next
    return {
        "session_id": session_id,
        "status": "awaiting_hitl" if awaiting else values.get("status", "completed"),
        "report_json": values.get("report_json"),
        "output": _public_output(values),
    }


def _persist_document(supabase_client: Any, user_id: str, agent_type: str, values: dict[str, Any]) -> None:
    try:
        supabase_client.table("generated_documents").insert({
            "user_id": user_id,
            "agent_type": agent_type,
            "storage_path": values.get("pdf_storage_path", ""),
            "signed_url": values.get("signed_url"),
            "url_expires_at": values.get("url_expires_at"),
        }).execute()
    except Exception as exc:
        log.warning("generated_document_persist_failed", error=str(exc))


# ── Grant Draft Generator ────────────────────────────────────────────────────
# Single-shot intake (programme_name + business_profile arrive together in
# the start payload), same billing-on-confirm HITL shape as compliance-drafter:
# credits are deducted only after the user approves the draft preview (see
# confirm_grant_draft_generator + agents.py's generalised /confirm dispatch).


async def start_grant_draft_generator(
    *,
    user_id: str,
    payload: dict[str, Any],
    supabase_client: Any,
    checkpointer: Any,
) -> dict[str, Any]:
    session_id = str(uuid.uuid4())
    graph = get_grant_draft_generator_graph(checkpointer=checkpointer)
    inputs: GrantDraftState = {
        "session_id": session_id,
        "user_id": user_id,
        "programme_name": payload.get("programme_name", ""),
        "business_profile": payload.get("business_profile") or {},
        "language": payload.get("language", "bm"),
        "export_format": payload.get("export_format", "pdf"),
        "turns_count": 0,
        "tool_calls": [],
        "_supabase": supabase_client,
    }
    values, awaiting = await _run_graph(graph, session_id, inputs)
    status = "error" if values.get("error") else ("awaiting_hitl" if awaiting else "completed")
    _log_run(supabase_client, user_id, "grant-draft-generator", session_id, payload, values, values.get("latency_ms", 0), status)
    resp = _base_response(session_id, values, awaiting=awaiting)
    resp["status"] = status
    resp["awaiting_hitl"] = bool(awaiting) and not values.get("error")
    resp["report_json"] = values.get("report_json")
    if values.get("error"):
        resp["error"] = values["error"]
    return resp


async def confirm_grant_draft_generator(
    *,
    session_id: str,
    user_id: str,
    user_email: Optional[str],
    supabase_client: Any,
    checkpointer: Any,
) -> dict[str, Any]:
    graph = get_grant_draft_generator_graph(checkpointer=checkpointer)
    await graph.aupdate_state(_thread_config(session_id), {"_supabase": supabase_client, "_user_email": user_email})
    values, _ = await _run_graph(graph, session_id, {}, resume=True)
    status = "error" if values.get("error") else "completed"
    _log_run(supabase_client, user_id, "grant-draft-generator", session_id, {"confirm": True}, values, values.get("latency_ms", 0), status)
    if supabase_client and (values.get("pdf_storage_path") or values.get("docx_storage_path")):
        _persist_document(supabase_client, user_id, "grant-draft-generator", {
            "pdf_storage_path": values.get("pdf_storage_path") or values.get("docx_storage_path"),
            "signed_url": values.get("signed_url"),
            "url_expires_at": values.get("url_expires_at"),
        })
    resp = _base_response(session_id, values)
    resp["status"] = status
    resp["signed_url"] = values.get("signed_url")
    resp["url_expires_at"] = values.get("url_expires_at")
    resp["email_sent"] = values.get("email_sent", False)
    if values.get("error"):
        resp["error"] = values["error"]
    return resp


async def get_grant_draft_status(session_id: str, checkpointer: Any) -> dict[str, Any]:
    graph = get_grant_draft_generator_graph(checkpointer=checkpointer)
    snapshot = await graph.aget_state(_thread_config(session_id))
    if not snapshot or not snapshot.values:
        return {"session_id": session_id, "status": "not_found"}
    values = dict(snapshot.values)
    awaiting = snapshot.next
    return {
        "session_id": session_id,
        "status": "awaiting_hitl" if awaiting else values.get("status", "completed"),
        "report_json": values.get("report_json"),
        "output": _public_output(values),
    }


# ── Study Agent ───────────────────────────────────────────────────────────────


async def start_study_agent(*, user_id: str, payload: dict[str, Any], supabase_client: Any, checkpointer: Any) -> dict[str, Any]:
    session_id = str(uuid.uuid4())
    graph = get_study_agent_graph(checkpointer=checkpointer)
    inputs = {
        "session_id": session_id,
        "user_id": user_id,
        "subject": payload.get("subject", "sejarah"),
        "paper_text": payload.get("paper_text", ""),
        "document_base64": payload.get("document_base64", ""),
        "message": payload.get("message", ""),
        "language": payload.get("language", "bm"),
        "turns_count": 0,
        "tool_calls": [],
    }
    values, _ = await _run_graph(graph, session_id, inputs)
    _log_run(supabase_client, user_id, "study-agent", session_id, payload, values, values.get("latency_ms", 0), "completed")
    return _base_response(session_id, values)


async def continue_study_agent(*, session_id: str, payload: dict[str, Any], checkpointer: Any) -> dict[str, Any]:
    from app.agents.study_agent.nodes import explain_node, track_topics_node

    graph = get_study_agent_graph(checkpointer=checkpointer)
    snapshot = await graph.aget_state(_thread_config(session_id))
    if not snapshot or not snapshot.values:
        return {"session_id": session_id, "status": "not_found"}
    state = dict(snapshot.values)
    state["message"] = payload.get("message", state.get("message", ""))
    if payload.get("question_index") is not None:
        state["active_question_index"] = payload["question_index"]
    state["turns_count"] = int(state.get("turns_count") or 0) + 1
    t0 = time.monotonic()
    state.update(await explain_node(state))
    state.update(await track_topics_node(state))
    await graph.aupdate_state(_thread_config(session_id), state)
    state["latency_ms"] = round((time.monotonic() - t0) * 1000)
    return _base_response(session_id, state)


async def get_study_status(session_id: str, checkpointer: Any) -> dict[str, Any]:
    graph = get_study_agent_graph(checkpointer=checkpointer)
    snapshot = await graph.aget_state(_thread_config(session_id))
    if not snapshot or not snapshot.values:
        return {"session_id": session_id, "status": "not_found"}
    return {"session_id": session_id, "status": "completed", "output": _public_output(dict(snapshot.values))}


# ── Immigration Navigator ─────────────────────────────────────────────────────


async def start_immigration_navigator(*, user_id: str, payload: dict[str, Any], supabase_client: Any, checkpointer: Any) -> dict[str, Any]:
    session_id = str(uuid.uuid4())
    graph = get_immigration_navigator_graph(checkpointer=checkpointer)
    inputs = {
        "session_id": session_id,
        "user_id": user_id,
        "message": payload.get("message", ""),
        "language": payload.get("language", "bm"),
        "turns_count": 0,
        "tool_calls": [],
    }
    values, _ = await _run_graph(graph, session_id, inputs)
    status = values.get("status", "completed")
    _log_run(supabase_client, user_id, "immigration-navigator", session_id, payload, values, values.get("latency_ms", 0), status)
    resp = _base_response(session_id, values)
    if status == "needs_input":
        resp["next_prompt"] = values.get("next_prompt")
    return resp


async def continue_immigration_navigator(*, session_id: str, payload: dict[str, Any], supabase_client: Any, checkpointer: Any) -> dict[str, Any]:
    graph = get_immigration_navigator_graph(checkpointer=checkpointer)
    await graph.aupdate_state(_thread_config(session_id), {"message": payload.get("message", "")})
    t0 = time.monotonic()
    await graph.ainvoke(None, config=_thread_config(session_id))
    snapshot = await graph.aget_state(_thread_config(session_id))
    values = dict(snapshot.values) if snapshot else {}
    values["latency_ms"] = round((time.monotonic() - t0) * 1000)
    status = values.get("status", "completed")
    user_id = values.get("user_id") or ""
    _log_run(supabase_client, user_id, "immigration-navigator", session_id, payload, values, values.get("latency_ms", 0), status)
    resp = _base_response(session_id, values)
    if status == "needs_input":
        resp["next_prompt"] = values.get("next_prompt")
    return resp


async def get_immigration_status(session_id: str, checkpointer: Any) -> dict[str, Any]:
    graph = get_immigration_navigator_graph(checkpointer=checkpointer)
    snapshot = await graph.aget_state(_thread_config(session_id))
    if not snapshot or not snapshot.values:
        return {"session_id": session_id, "status": "not_found"}
    values = dict(snapshot.values)
    return {"session_id": session_id, "status": values.get("status", "completed"), "output": _public_output(values)}


async def start_retrenchment_navigator(*, user_id: str, payload: dict[str, Any], supabase_client: Any, checkpointer: Any) -> dict[str, Any]:
    session_id = str(uuid.uuid4())
    graph = get_retrenchment_navigator_graph(checkpointer=checkpointer)
    inputs = {
        "session_id": session_id,
        "user_id": user_id,
        "message": payload.get("message", ""),
        "language": payload.get("language", "bm"),
        "turns_count": 0,
        "tool_calls": [],
    }
    values, _ = await _run_graph(graph, session_id, inputs)
    status = values.get("status", "completed")
    _log_run(supabase_client, user_id, "retrenchment-navigator", session_id, payload, values, values.get("latency_ms", 0), status)
    resp = _base_response(session_id, values)
    if status == "needs_input":
        resp["next_prompt"] = values.get("next_prompt")
    return resp


async def continue_retrenchment_navigator(*, session_id: str, payload: dict[str, Any], supabase_client: Any, checkpointer: Any) -> dict[str, Any]:
    graph = get_retrenchment_navigator_graph(checkpointer=checkpointer)
    await graph.aupdate_state(_thread_config(session_id), {"message": payload.get("message", "")})
    t0 = time.monotonic()
    await graph.ainvoke(None, config=_thread_config(session_id))
    snapshot = await graph.aget_state(_thread_config(session_id))
    values = dict(snapshot.values) if snapshot else {}
    values["latency_ms"] = round((time.monotonic() - t0) * 1000)
    status = values.get("status", "completed")
    user_id = values.get("user_id") or ""
    _log_run(supabase_client, user_id, "retrenchment-navigator", session_id, payload, values, values.get("latency_ms", 0), status)
    resp = _base_response(session_id, values)
    if status == "needs_input":
        resp["next_prompt"] = values.get("next_prompt")
    return resp


async def get_retrenchment_status(session_id: str, checkpointer: Any) -> dict[str, Any]:
    graph = get_retrenchment_navigator_graph(checkpointer=checkpointer)
    snapshot = await graph.aget_state(_thread_config(session_id))
    if not snapshot or not snapshot.values:
        return {"session_id": session_id, "status": "not_found"}
    values = dict(snapshot.values)
    return {"session_id": session_id, "status": values.get("status", "completed"), "output": _public_output(values)}


# ── Health Triage ─────────────────────────────────────────────────────────────


async def start_health_triage(*, user_id: str, payload: dict[str, Any], supabase_client: Any, checkpointer: Any) -> dict[str, Any]:
    session_id = str(uuid.uuid4())
    graph = get_health_triage_graph(checkpointer=checkpointer)
    inputs = {
        "session_id": session_id,
        "user_id": user_id,
        "message": payload.get("message", ""),
        "language": payload.get("language", "bm"),
        "tool_calls": [],
    }
    values, _ = await _run_graph(graph, session_id, inputs)
    _log_run(supabase_client, user_id, "health-triage", session_id, payload, values, values.get("latency_ms", 0), "completed")
    return _base_response(session_id, values)


async def get_health_status(session_id: str, checkpointer: Any) -> dict[str, Any]:
    graph = get_health_triage_graph(checkpointer=checkpointer)
    snapshot = await graph.aget_state(_thread_config(session_id))
    if not snapshot or not snapshot.values:
        return {"session_id": session_id, "status": "not_found"}
    return {"session_id": session_id, "status": "completed", "output": _public_output(dict(snapshot.values))}


# ── Eligibility Agent ────────────────────────────────────────────────────────
# Multi-turn: intake spans several turns before the graph reaches grant_rag +
# analyst, so this agent needs both a start and a continue handler (unlike
# the single-shot grant-finder it replaces).


async def start_eligibility_agent(*, user_id: str, payload: dict[str, Any], supabase_client: Any, checkpointer: Any) -> dict[str, Any]:
    session_id = str(uuid.uuid4())
    graph = get_eligibility_agent_graph(checkpointer=checkpointer)
    business_profile: dict[str, Any] = {}
    for key in ("business_type", "sector", "annual_revenue_myr", "is_bumiputera", "registered_months"):
        if payload.get(key) is not None:
            business_profile[key] = payload[key]
    inputs = {
        "session_id": session_id,
        "user_id": user_id,
        "language": payload.get("language", "bm"),
        "current_turn": 0,
        "messages": [],
        "latest_user_input": payload.get("message", ""),
        "business_profile": business_profile or None,
        "intake_complete": False,
        "needs_more_info": True,
        "needs_clarification": False,
        "_supabase": supabase_client,
    }
    values, awaiting = await _run_graph(graph, session_id, inputs)
    status = "completed" if values.get("intake_complete") else "awaiting_hitl"
    _log_run(supabase_client, user_id, "eligibility-agent", session_id, payload, values, values.get("latency_ms", 0), status)
    resp = _base_response(session_id, values, awaiting=awaiting)
    resp["status"] = status
    resp["awaiting_hitl"] = not values.get("intake_complete", False)
    resp["output"] = {
        "next_question": values.get("next_question"),
        "matched_grants": values.get("matched_grants", []),
        "near_miss_grants": values.get("near_miss_grants", []),
        "stacking_matrix": values.get("stacking_matrix"),
    }
    return resp


async def continue_eligibility_agent(*, session_id: str, payload: dict[str, Any], checkpointer: Any) -> dict[str, Any]:
    graph = get_eligibility_agent_graph(checkpointer=checkpointer)
    await graph.aupdate_state(_thread_config(session_id), {"latest_user_input": payload.get("message", "")})
    t0 = time.monotonic()
    await graph.ainvoke(None, config=_thread_config(session_id))
    latency_ms = round((time.monotonic() - t0) * 1000)
    snapshot = await graph.aget_state(_thread_config(session_id))
    values = dict(snapshot.values) if snapshot else {}
    values["latency_ms"] = latency_ms
    awaiting = snapshot.next if snapshot else ()
    status = "completed" if values.get("intake_complete") else "awaiting_hitl"
    resp = _base_response(session_id, values, awaiting=awaiting)
    resp["status"] = status
    resp["awaiting_hitl"] = not values.get("intake_complete", False)
    resp["output"] = {
        "next_question": values.get("next_question"),
        "matched_grants": values.get("matched_grants", []),
        "near_miss_grants": values.get("near_miss_grants", []),
        "stacking_matrix": values.get("stacking_matrix"),
    }
    return resp


# ── Research Synthesiser ──────────────────────────────────────────────────────


async def start_research_synthesiser(*, user_id: str, payload: dict[str, Any], supabase_client: Any, checkpointer: Any) -> dict[str, Any]:
    session_id = str(uuid.uuid4())
    graph = get_research_synthesiser_graph()
    inputs = {
        "query": payload.get("query", ""),
        "language": payload.get("language", "bm"),
        "domain_results": [],
    }
    t0 = time.monotonic()
    values = await graph.ainvoke(inputs)
    values["latency_ms"] = round((time.monotonic() - t0) * 1000)
    _log_run(supabase_client, user_id, "research-synthesiser", session_id, payload, values, values.get("latency_ms", 0), "completed")
    return {
        "session_id": session_id,
        "status": "completed",
        "output": _public_output(values),
        "citations": values.get("merged_citations") or values.get("citations") or [],
        "detected_domains": values.get("detected_domains") or [],
    }


# ── SME Compliance Navigator (PatuhiKu) ─────────────────────────────────────


async def start_sme_compliance_navigator(*, user_id: str, payload: dict[str, Any], supabase_client: Any, checkpointer: Any) -> dict[str, Any]:
    session_id = str(uuid.uuid4())
    graph = get_sme_compliance_navigator_graph()
    inputs = {
        "session_id": session_id,
        "user_id": user_id,
        "business_profile": payload.get("business_profile", ""),
        "language": payload.get("language", "bm"),
        "domain_results": [],
    }
    t0 = time.monotonic()
    values = await graph.ainvoke(inputs)
    values["latency_ms"] = round((time.monotonic() - t0) * 1000)
    _log_run(supabase_client, user_id, "sme-compliance-navigator", session_id, payload, values, values.get("latency_ms", 0), "completed")
    return {
        "session_id": session_id,
        "status": "completed",
        "output": _public_output(values),
        "checklist": values.get("checklist") or [],
        "stale_warnings": values.get("stale_warnings") or [],
        "triggered_domains": values.get("triggered_domains") or [],
    }


# ── Dispatch table ────────────────────────────────────────────────────────────

AGENT_START_HANDLERS: dict[str, Callable[..., Any]] = {
    "compliance-drafter": start_compliance_drafter,
    "sme-compliance-navigator": start_sme_compliance_navigator,
    "study-agent": start_study_agent,
    "immigration-navigator": start_immigration_navigator,
    "health-triage": start_health_triage,
    "eligibility-agent": start_eligibility_agent,
    "research-synthesiser": start_research_synthesiser,
    "grant-draft-generator": start_grant_draft_generator,
    "retrenchment-navigator": start_retrenchment_navigator,
}

AGENT_CONTINUE_HANDLERS: dict[str, Callable[..., Any]] = {
    "compliance-drafter": continue_compliance_drafter,
    "study-agent": continue_study_agent,
    "immigration-navigator": continue_immigration_navigator,
    "eligibility-agent": continue_eligibility_agent,
    "retrenchment-navigator": continue_retrenchment_navigator,
}

AGENT_STATUS_HANDLERS: dict[str, Callable[..., Any]] = {
    "compliance-drafter": get_compliance_status,
    "study-agent": get_study_status,
    "immigration-navigator": get_immigration_status,
    "health-triage": get_health_status,
    "grant-draft-generator": get_grant_draft_status,
    "retrenchment-navigator": get_retrenchment_status,
}

# agent_name -> confirm handler. Every entry here is dispatched generically
# by agents.py's /confirm endpoint (billing happens here, after HITL preview
# approval — never at start). Keep the kwargs shape (session_id, user_id,
# user_email, supabase_client, checkpointer) identical across entries so the
# router can call them uniformly.
AGENT_CONFIRM_HANDLERS: dict[str, Callable[..., Any]] = {
    "compliance-drafter": confirm_compliance_drafter,
    "grant-draft-generator": confirm_grant_draft_generator,
}

CREDIT_ON_COMPLETE_AGENTS = frozenset({"immigration-navigator"})
