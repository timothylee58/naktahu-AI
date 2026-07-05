"""Product-agent HTTP endpoints — start, continue, confirm, status, deadlines."""
from __future__ import annotations

from typing import Annotated, Any, Literal, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.agents.checkpointer import get_checkpointer
from app.services.agent_runner import (
    confirm_compliance_drafter,
    continue_compliance_drafter,
    get_compliance_status,
    start_compliance_drafter,
)
from middleware.plan_gate import require_plan
from services.agent_registry import get_agent, is_credit_exempt, plan_satisfies
from services.auth import UserContext, get_current_user
from services.billing import deduct_credits, get_credits_remaining

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])


class AgentStartRequest(BaseModel):
    business_type: str = "sole_proprietor"
    domains: list[str] = Field(default_factory=lambda: ["tax", "business", "epf"])
    context: str = ""
    language: Literal["bm", "en", "zh"] = "bm"


class AgentContinueRequest(BaseModel):
    session_id: str
    context: Optional[str] = None
    business_type: Optional[str] = None
    domains: Optional[list[str]] = None


class AgentConfirmRequest(BaseModel):
    session_id: str


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
    if cost <= 0 or is_credit_exempt(user.plan, agent_name):
        return
    sb = getattr(request.app.state, "supabase", None)
    remaining = await get_credits_remaining(sb, user.user_id)
    if remaining < cost:
        raise HTTPException(status_code=402, detail="Insufficient agent credits. Top up to continue.")


@router.post("/{agent_name}/start")
async def agent_start(
    agent_name: str,
    body: AgentStartRequest,
    request: Request,
    user: Annotated[UserContext, Depends(get_current_user)],
) -> dict[str, Any]:
    agent = _require_agent_access(agent_name, user)
    await _ensure_credits(request, user, agent_name, agent.credit_cost)

    if agent_name != "compliance-drafter":
        raise HTTPException(status_code=501, detail=f"Agent '{agent_name}' is not yet implemented.")

    cp = getattr(request.app.state, "checkpointer", None) or get_checkpointer()
    result = await start_compliance_drafter(
        user_id=user.user_id,
        user_email=user.email,
        payload=body.model_dump(),
        supabase_client=getattr(request.app.state, "supabase", None),
        checkpointer=cp,
    )
    log.info("agent_started", agent=agent_name, session_id=result["session_id"], user_id=user.user_id)
    return result


@router.post("/{agent_name}/continue")
async def agent_continue(
    agent_name: str,
    body: AgentContinueRequest,
    request: Request,
    user: Annotated[UserContext, Depends(get_current_user)],
) -> dict[str, Any]:
    _require_agent_access(agent_name, user)
    if agent_name != "compliance-drafter":
        raise HTTPException(status_code=501, detail=f"Agent '{agent_name}' is not yet implemented.")

    cp = getattr(request.app.state, "checkpointer", None) or get_checkpointer()
    return await continue_compliance_drafter(
        session_id=body.session_id,
        user_id=user.user_id,
        payload=body.model_dump(exclude_none=True),
        checkpointer=cp,
    )


@router.post("/{agent_name}/confirm")
async def agent_confirm(
    agent_name: str,
    body: AgentConfirmRequest,
    request: Request,
    user: Annotated[UserContext, Depends(get_current_user)],
) -> dict[str, Any]:
    agent = _require_agent_access(agent_name, user)
    if agent_name != "compliance-drafter":
        raise HTTPException(status_code=501, detail=f"Agent '{agent_name}' is not yet implemented.")

    sb = getattr(request.app.state, "supabase", None)
    if agent.credit_cost > 0 and not is_credit_exempt(user.plan, agent_name):
        remaining = await get_credits_remaining(sb, user.user_id)
        if remaining < agent.credit_cost:
            raise HTTPException(status_code=402, detail="Insufficient agent credits.")

    cp = getattr(request.app.state, "checkpointer", None) or get_checkpointer()
    result = await confirm_compliance_drafter(
        session_id=body.session_id,
        user_id=user.user_id,
        user_email=user.email,
        supabase_client=sb,
        checkpointer=cp,
    )
    if agent.credit_cost > 0 and not is_credit_exempt(user.plan, agent_name):
        remaining = await deduct_credits(sb, user.user_id, agent.credit_cost)
        if remaining < 0:
            log.warning("agent_confirm_credit_deduct_failed", user_id=user.user_id)
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
    if agent_name != "compliance-drafter":
        raise HTTPException(status_code=501, detail=f"Agent '{agent_name}' is not yet implemented.")

    cp = getattr(request.app.state, "checkpointer", None) or get_checkpointer()
    return await get_compliance_status(session_id, cp)


@router.get("/compliance-drafter/preview/{session_id}")
async def compliance_preview(
    session_id: str,
    request: Request,
    user: Annotated[UserContext, Depends(get_current_user)],
) -> dict[str, Any]:
    _require_agent_access("compliance-drafter", user)
    cp = getattr(request.app.state, "checkpointer", None) or get_checkpointer()
    status = await get_compliance_status(session_id, cp)
    if status.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="Session not found.")
    return {"session_id": session_id, "report": status.get("report_json")}


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
