"""Orchestrate product-agent graph runs, checkpoints, and audit logging."""
from __future__ import annotations

import time
import uuid
from typing import Any, Optional

import structlog
from langgraph.types import Command

from app.agents.compliance_drafter.graph import get_compliance_drafter_graph
from app.agents.compliance_drafter.state import ComplianceDrafterState

log = structlog.get_logger(__name__)

AGENT_GRAPH_BUILDERS = {
    "compliance-drafter": get_compliance_drafter_graph,
}


def _thread_config(session_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": session_id}}


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
    t0 = time.monotonic()
    await graph.ainvoke(inputs, config=_thread_config(session_id))
    latency_ms = round((time.monotonic() - t0) * 1000)
    snapshot = await graph.aget_state(_thread_config(session_id))
    values = dict(snapshot.values) if snapshot else {}
    awaiting = snapshot.next if snapshot else ()
    _log_run(supabase_client, user_id, session_id, payload, values, latency_ms, "awaiting_hitl" if awaiting else "completed")
    return {
        "session_id": session_id,
        "status": "awaiting_hitl" if awaiting else "completed",
        "awaiting_hitl": bool(awaiting),
        "report_json": values.get("report_json"),
        "turns_count": values.get("turns_count", 1),
    }


async def continue_compliance_drafter(
    *,
    session_id: str,
    user_id: str,
    payload: dict[str, Any],
    checkpointer: Any,
) -> dict[str, Any]:
    graph = get_compliance_drafter_graph(checkpointer=checkpointer)
    update: dict[str, Any] = {}
    if payload.get("context"):
        update["context"] = payload["context"]
    if payload.get("business_type"):
        update["business_type"] = payload["business_type"]
    if payload.get("domains"):
        update["domains"] = payload["domains"]
    if update:
        await graph.aupdate_state(_thread_config(session_id), update)
    t0 = time.monotonic()
    await graph.ainvoke(None, config=_thread_config(session_id))
    latency_ms = round((time.monotonic() - t0) * 1000)
    snapshot = await graph.aget_state(_thread_config(session_id))
    values = dict(snapshot.values) if snapshot else {}
    awaiting = snapshot.next if snapshot else ()
    return {
        "session_id": session_id,
        "status": "awaiting_hitl" if awaiting else "completed",
        "report_json": values.get("report_json"),
        "latency_ms": latency_ms,
        "turns_count": values.get("turns_count", 1),
    }


async def confirm_compliance_drafter(
    *,
    session_id: str,
    user_id: str,
    user_email: Optional[str],
    supabase_client: Any,
    checkpointer: Any,
) -> dict[str, Any]:
    graph = get_compliance_drafter_graph(checkpointer=checkpointer)
    await graph.aupdate_state(
        _thread_config(session_id),
        {"_supabase": supabase_client, "_user_email": user_email},
    )
    t0 = time.monotonic()
    await graph.ainvoke(Command(resume=True), config=_thread_config(session_id))
    latency_ms = round((time.monotonic() - t0) * 1000)
    snapshot = await graph.aget_state(_thread_config(session_id))
    values = dict(snapshot.values) if snapshot else {}
    _log_run(supabase_client, user_id, session_id, {"confirm": True}, values, latency_ms, "completed")
    if supabase_client and values.get("pdf_storage_path"):
        _persist_document(supabase_client, user_id, values)
    return {
        "session_id": session_id,
        "status": "completed",
        "signed_url": values.get("signed_url"),
        "url_expires_at": values.get("url_expires_at"),
        "email_sent": values.get("email_sent", False),
        "latency_ms": latency_ms,
    }


async def get_compliance_status(session_id: str, checkpointer: Any) -> dict[str, Any]:
    graph = get_compliance_drafter_graph(checkpointer=checkpointer)
    snapshot = await graph.aget_state(_thread_config(session_id))
    if not snapshot or not snapshot.values:
        return {"session_id": session_id, "status": "not_found"}
    values = dict(snapshot.values)
    awaiting = snapshot.next
    return {
        "session_id": session_id,
        "status": "awaiting_hitl" if awaiting else "completed",
        "report_json": values.get("report_json"),
        "signed_url": values.get("signed_url"),
        "turns_count": values.get("turns_count", 0),
    }


def _log_run(
    supabase_client: Any,
    user_id: str,
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
            "agent_name": "compliance-drafter",
            "session_id": session_id,
            "input": input_payload,
            "output": {
                "report_json": output.get("report_json"),
                "signed_url": output.get("signed_url"),
            },
            "turns_count": output.get("turns_count", 1),
            "tool_calls": output.get("tool_calls") or [],
            "completion_status": status,
            "latency_ms": latency_ms,
        }).execute()
    except Exception as exc:
        log.warning("agent_run_log_failed", error=str(exc))


def _persist_document(supabase_client: Any, user_id: str, values: dict[str, Any]) -> None:
    try:
        supabase_client.table("generated_documents").insert({
            "user_id": user_id,
            "agent_type": "compliance-drafter",
            "storage_path": values.get("pdf_storage_path"),
            "signed_url": values.get("signed_url"),
            "url_expires_at": values.get("url_expires_at"),
        }).execute()
    except Exception as exc:
        log.warning("generated_document_persist_failed", error=str(exc))
