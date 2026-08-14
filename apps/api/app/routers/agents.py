"""Product-agent HTTP endpoints — start, continue, confirm, status, deadlines."""
from __future__ import annotations

from typing import Annotated, Any, Literal, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.agents.checkpointer import get_checkpointer
from app.services.agent_runner import (
    AGENT_CONFIRM_HANDLERS,
    AGENT_CONTINUE_HANDLERS,
    AGENT_START_HANDLERS,
    AGENT_STATUS_HANDLERS,
    CREDIT_ON_COMPLETE_AGENTS,
    export_health_triage,
    get_compliance_status,
)
from middleware.plan_gate import require_plan
from services.agent_registry import get_agent, is_credit_exempt, list_agents, plan_satisfies
from services.auth import UserContext, get_current_user
from services.billing import deduct_credits, get_credits_remaining

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])


class AgentStartRequest(BaseModel):
    language: Literal["bm", "en", "zh"] = "bm"
    message: str = ""
    context: str = ""
    query: Optional[str] = None
    # compliance-drafter
    business_type: str = "sole_proprietor"
    domains: list[str] = Field(default_factory=lambda: ["tax", "business", "epf"])
    # study-agent
    subject: str = "sejarah"
    level: Literal["spm", "stpm", "a-level"] = "spm"
    mode: Literal["explain", "quiz"] = "explain"
    paper_text: str = Field(default="", max_length=20_000)
    document_base64: str = Field(default="", max_length=15_000_000)
    image_base64: str = Field(default="", max_length=15_000_000)
    image_mime_type: str = "image/jpeg"
    # eligibility-agent (business_type/message/language shared with other agents above)
    sector: str = ""
    annual_revenue_myr: Optional[float] = None
    is_bumiputera: Optional[bool] = None
    registered_months: Optional[int] = None
    # grant-draft-generator
    programme_name: str = ""
    business_profile: dict[str, Any] = Field(default_factory=dict)
    export_format: Literal["pdf", "docx"] = "pdf"


class AgentContinueRequest(BaseModel):
    session_id: str
    message: Optional[str] = None
    context: Optional[str] = None
    business_type: Optional[str] = None
    domains: Optional[list[str]] = None
    question_index: Optional[int] = None


class AgentConfirmRequest(BaseModel):
    session_id: str
    # grant-draft-generator only — user-edited draft text applied before the
    # PDF/DOCX is generated. Other confirm handlers accept and ignore it.
    edits: Optional[dict[str, Any]] = None


def _require_agent_access(agent_name: str, user: UserContext) -> Any:
    agent = get_agent(agent_name)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Unknown agent: {agent_name}")
    if not plan_satisfies(user.plan, agent.plan_required):
        raise HTTPException(
            status_code=403,
            detail=f"This agent requires the {agent.plan_required} plan or higher.",
        )
    return agent


async def _ensure_credits(request: Request, user: UserContext, agent_name: str, cost: int) -> None:
    if cost <= 0 or is_credit_exempt(user.plan, agent_name, role=user.role):
        return
    sb = getattr(request.app.state, "supabase", None)
    remaining = await get_credits_remaining(sb, user.user_id)
    if remaining < cost:
        raise HTTPException(status_code=402, detail="Insufficient agent credits. Top up to continue.")


def _checkpointer(request: Request) -> Any:
    return getattr(request.app.state, "checkpointer", None) or get_checkpointer()


@router.get("")
async def list_available_agents(
    user: Annotated[UserContext, Depends(get_current_user)],
) -> list[dict[str, Any]]:
    return [
        {
            "name": a.name,
            "description": a.description,
            "plan_required": a.plan_required,
            "credit_cost": a.credit_cost,
            "accessible": plan_satisfies(user.plan, a.plan_required),
        }
        for a in list_agents()
    ]


@router.post("/{agent_name}/start")
async def agent_start(
    agent_name: str,
    body: AgentStartRequest,
    request: Request,
    user: Annotated[UserContext, Depends(get_current_user)],
) -> dict[str, Any]:
    agent = _require_agent_access(agent_name, user)
    handler = AGENT_START_HANDLERS.get(agent_name)
    if not handler:
        raise HTTPException(status_code=501, detail=f"Agent '{agent_name}' is not yet implemented.")

    if agent_name not in CREDIT_ON_COMPLETE_AGENTS:
        await _ensure_credits(request, user, agent_name, agent.credit_cost)

    payload = body.model_dump()
    cp = _checkpointer(request)
    sb = getattr(request.app.state, "supabase", None)

    kwargs: dict[str, Any] = {
        "user_id": user.user_id,
        "payload": payload,
        "supabase_client": sb,
        "checkpointer": cp,
    }
    if agent_name == "compliance-drafter":
        kwargs["user_email"] = user.email

    result = await handler(**kwargs)

    if agent_name in CREDIT_ON_COMPLETE_AGENTS and result.get("status") == "completed":
        if agent.credit_cost > 0 and not is_credit_exempt(user.plan, agent_name, role=user.role):
            remaining = await deduct_credits(sb, user.user_id, agent.credit_cost)
            if remaining < 0:
                raise HTTPException(status_code=402, detail="Insufficient agent credits.")
            result["credits_remaining"] = remaining

    log.info("agent_started", agent=agent_name, session_id=result.get("session_id"), user_id=user.user_id)
    return result


@router.post("/{agent_name}/continue")
async def agent_continue(
    agent_name: str,
    body: AgentContinueRequest,
    request: Request,
    user: Annotated[UserContext, Depends(get_current_user)],
) -> dict[str, Any]:
    _require_agent_access(agent_name, user)
    handler = AGENT_CONTINUE_HANDLERS.get(agent_name)
    if not handler:
        raise HTTPException(status_code=501, detail=f"Agent '{agent_name}' does not support continue.")

    cp = _checkpointer(request)
    sb = getattr(request.app.state, "supabase", None)
    kwargs: dict[str, Any] = {
        "session_id": body.session_id,
        "payload": body.model_dump(exclude_none=True),
        "checkpointer": cp,
    }
    # Only compliance-drafter's continue handler accepts user_id — the rest
    # derive it from checkpointed state instead (see agent_runner.py).
    # Passing it here raised TypeError on every second-and-later turn
    # (Cursor Bugbot finding, verified by reading the handler signatures
    # directly).
    if agent_name == "compliance-drafter":
        kwargs["user_id"] = user.user_id
    if agent_name in (
        "immigration-navigator",
        "retrenchment-navigator",
        "study-agent",
        "eligibility-agent",
        "compliance-drafter",
    ):
        kwargs["supabase_client"] = sb

    result = await handler(**kwargs)

    if agent_name in CREDIT_ON_COMPLETE_AGENTS and result.get("status") == "completed":
        agent = get_agent(agent_name)
        if agent and agent.credit_cost > 0 and not is_credit_exempt(user.plan, agent_name, role=user.role):
            remaining = await deduct_credits(sb, user.user_id, agent.credit_cost)
            result["credits_remaining"] = remaining

    return result


@router.post("/{agent_name}/confirm")
async def agent_confirm(
    agent_name: str,
    body: AgentConfirmRequest,
    request: Request,
    user: Annotated[UserContext, Depends(get_current_user)],
) -> dict[str, Any]:
    agent = _require_agent_access(agent_name, user)
    handler = AGENT_CONFIRM_HANDLERS.get(agent_name)
    if not handler:
        raise HTTPException(status_code=501, detail=f"Agent '{agent_name}' does not support confirm.")

    sb = getattr(request.app.state, "supabase", None)
    if agent.credit_cost > 0 and not is_credit_exempt(user.plan, agent_name, role=user.role):
        remaining = await get_credits_remaining(sb, user.user_id)
        if remaining < agent.credit_cost:
            raise HTTPException(status_code=402, detail="Insufficient agent credits.")

    result = await handler(
        session_id=body.session_id,
        user_id=user.user_id,
        user_email=user.email,
        supabase_client=sb,
        checkpointer=_checkpointer(request),
        edits=body.edits,
    )
    if agent.credit_cost > 0 and not is_credit_exempt(user.plan, agent_name, role=user.role):
        remaining = await deduct_credits(sb, user.user_id, agent.credit_cost)
        if remaining < 0:
            log.warning("agent_confirm_credit_deduct_failed", user_id=user.user_id)
        result["credits_remaining"] = remaining

    log.info("agent_confirmed", agent=agent_name, session_id=body.session_id, user_id=user.user_id)
    return result


@router.get("/{agent_name}/status/{session_id}")
async def agent_status(
    agent_name: str,
    session_id: str,
    request: Request,
    user: Annotated[UserContext, Depends(get_current_user)],
) -> dict[str, Any]:
    _require_agent_access(agent_name, user)
    handler = AGENT_STATUS_HANDLERS.get(agent_name)
    if not handler:
        raise HTTPException(status_code=501, detail=f"Agent '{agent_name}' status not available.")
    return await handler(session_id, _checkpointer(request))


@router.get("/compliance-drafter/preview/{session_id}")
async def compliance_preview(
    session_id: str,
    request: Request,
    user: Annotated[UserContext, Depends(get_current_user)],
) -> dict[str, Any]:
    _require_agent_access("compliance-drafter", user)
    status = await get_compliance_status(session_id, _checkpointer(request))
    if status.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="Session not found.")
    return {"session_id": session_id, "report": status.get("report_json") or status.get("output")}


@router.post("/health-triage/{session_id}/export")
async def export_health_triage_pdf(
    session_id: str,
    request: Request,
    user: Annotated[UserContext, Depends(get_current_user)],
) -> dict[str, Any]:
    """On-demand PDF export of a completed Health Triage session. Health
    Triage's graph has no HITL confirm step (unlike compliance-drafter/
    grant-draft-generator, which generate their PDF as part of the graph
    flow itself) — export here is a separate call after the fact instead,
    so this doesn't re-run the graph or the LLM, just formats state that's
    already there."""
    _require_agent_access("health-triage", user)
    sb = getattr(request.app.state, "supabase", None)
    if not sb:
        raise HTTPException(status_code=503, detail="Export is temporarily unavailable.")
    try:
        return await export_health_triage(
            session_id=session_id,
            checkpointer=_checkpointer(request),
            supabase_client=sb,
            user_id=user.user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{agent_name}/documents")
async def list_agent_documents(
    agent_name: str,
    request: Request,
    user: Annotated[UserContext, Depends(get_current_user)],
) -> list[dict[str, Any]]:
    """Recent generated files for this user + agent (grant-draft-generator,
    compliance-drafter) — backs a draft-history list in the frontend.
    Reads generated_documents, which _persist_document already writes to;
    no new table. Signed URLs may have expired by the time this is read,
    so the frontend must check url_expires_at before offering re-download."""
    _require_agent_access(agent_name, user)
    sb = getattr(request.app.state, "supabase", None)
    if not sb:
        raise HTTPException(status_code=503, detail="Document history is temporarily unavailable.")
    try:
        res = (
            sb.table("generated_documents")
            .select("id,storage_path,signed_url,url_expires_at,created_at")
            .eq("user_id", user.user_id)
            .eq("agent_type", agent_name)
            .order("created_at", desc=True)
            .limit(10)
            .execute()
        )
        return res.data or []
    except Exception as exc:
        log.warning("agent_documents_fetch_failed", agent=agent_name, error=str(exc))
        return []


@router.get("/deadline-monitor/deadlines")
async def list_deadlines(
    request: Request,
    user: Annotated[UserContext, Depends(require_plan("pro"))],
) -> list[dict[str, Any]]:
    sb = getattr(request.app.state, "supabase", None)
    if not sb:
        return []
    try:
        res = (
            sb.table("deadline_schedule")
            .select("id,domain,deadline_name,due_date,recurrence,source_url,last_verified")
            .order("due_date")
            .limit(50)
            .execute()
        )
        return res.data or []
    except Exception as exc:
        log.warning("deadline_fetch_failed", error=str(exc))
        return []
