"""Orchestration discovery and health endpoints.

Exposes the enhanced agent registry, capability search, and circuit breaker
health to the frontend and admin tools. These are read-only endpoints that
don't invoke agents — they're for discovery and monitoring.
"""
from __future__ import annotations

from typing import Annotated, Any, Optional

import structlog
from fastapi import APIRouter, Depends, Query, Request

from app.orchestration.circuit_breaker import get_all_breaker_metrics
from app.orchestration.registry import (
    find_agents_by_capability,
    find_agents_for_domain,
    get_best_agents_for_task,
    get_definition,
    list_definitions,
    plan_satisfies,
)
from app.orchestration.types import AgentCapability
from services.auth import UserContext, get_current_user, get_optional_user

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/orchestration", tags=["orchestration"])


@router.get("/agents")
async def list_orchestrated_agents(
    user: Annotated[Optional[UserContext], Depends(get_optional_user)],
) -> list[dict[str, Any]]:
    """List all registered agents with capability and access metadata.

    Returns enriched agent definitions including capabilities, supported
    domains, versioning, and whether the current user can access each agent.
    """
    user_plan = user.plan if user else "free"
    definitions = list_definitions()

    return [
        {
            "name": d.name,
            "version": d.version,
            "description": d.description,
            "capabilities": [c.value for c in d.capabilities],
            "supported_domains": d.supported_domains,
            "plan_required": d.plan_required,
            "credit_cost": d.credit_cost,
            "supports_multi_turn": d.supports_multi_turn,
            "supports_streaming": d.supports_streaming,
            "accessible": plan_satisfies(user_plan, d.plan_required),
            "deprecated": d.deprecated,
        }
        for d in definitions
    ]


@router.get("/agents/{agent_name}")
async def get_agent_details(
    agent_name: str,
    user: Annotated[Optional[UserContext], Depends(get_optional_user)],
) -> dict[str, Any]:
    """Get detailed information about a specific agent."""
    defn = get_definition(agent_name)
    if not defn:
        return {"error": f"Agent '{agent_name}' not found"}

    user_plan = user.plan if user else "free"
    return {
        "name": defn.name,
        "version": defn.version,
        "description": defn.description,
        "capabilities": [c.value for c in defn.capabilities],
        "supported_domains": defn.supported_domains,
        "plan_required": defn.plan_required,
        "credit_cost": defn.credit_cost,
        "supports_multi_turn": defn.supports_multi_turn,
        "supports_streaming": defn.supports_streaming,
        "max_timeout_seconds": defn.max_timeout_seconds,
        "input_schema": defn.input_schema,
        "output_schema": defn.output_schema,
        "accessible": plan_satisfies(user_plan, defn.plan_required),
        "deprecated": defn.deprecated,
        "successor": defn.successor,
    }


@router.get("/search")
async def search_agents(
    domain: Optional[str] = Query(None, description="Filter by supported domain"),
    capability: Optional[str] = Query(None, description="Filter by capability"),
    user: Optional[UserContext] = Depends(get_optional_user),
) -> list[dict[str, Any]]:
    """Search agents by domain or capability.

    Used by the frontend to suggest relevant agents based on the user's
    current query context.
    """
    results = []

    if domain:
        definitions = find_agents_for_domain(domain)
    elif capability:
        try:
            cap = AgentCapability(capability)
            definitions = find_agents_by_capability(cap)
        except ValueError:
            return []
    else:
        definitions = list_definitions()

    user_plan = user.plan if user else "free"
    for d in definitions:
        results.append({
            "name": d.name,
            "description": d.description,
            "capabilities": [c.value for c in d.capabilities],
            "supported_domains": d.supported_domains,
            "plan_required": d.plan_required,
            "accessible": plan_satisfies(user_plan, d.plan_required),
        })

    return results


@router.get("/recommend")
async def recommend_agents(
    query: str = Query(..., min_length=2, max_length=500, description="User query"),
    domain: str = Query("government", description="Target domain"),
    user: Optional[UserContext] = Depends(get_optional_user),
) -> list[dict[str, Any]]:
    """Recommend the best agents for a given query and domain.

    Returns ranked agents with fitness scores. Used by the orchestrator's
    planner and optionally exposed to the frontend for agent suggestions.
    """
    user_plan = user.plan if user else "free"

    # Infer needed capabilities from the query (simple heuristic for now;
    # Phase 2 will use the LLM planner for this).
    needed: list[AgentCapability] = []
    lower_query = query.lower()

    if any(k in lower_query for k in ("compliance", "report", "pdf", "laporan")):
        needed.append(AgentCapability.compliance_analysis)
    if any(k in lower_query for k in ("grant", "geran", "funding", "bantuan")):
        needed.append(AgentCapability.grant_matching)
    if any(k in lower_query for k in ("visa", "passport", "pasport", "immigration", "imigresen")):
        needed.append(AgentCapability.immigration_knowledge)
    if any(k in lower_query for k in ("health", "symptom", "doctor", "doktor", "sakit", "klinik")):
        needed.append(AgentCapability.symptom_triage)
    if any(k in lower_query for k in ("study", "spm", "exam", "peperiksaan", "belajar")):
        needed.append(AgentCapability.study_assistance)
    if any(k in lower_query for k in ("tax", "cukai", "lhdn")):
        needed.append(AgentCapability.tax_knowledge)
    if any(k in lower_query for k in ("epf", "kwsp")):
        needed.append(AgentCapability.epf_knowledge)

    # If no specific capabilities detected, default to general knowledge
    if not needed:
        needed.append(AgentCapability.government_knowledge)

    ranked = get_best_agents_for_task(domain, needed, user_plan, limit=5)

    return [
        {
            "name": defn.name,
            "description": defn.description,
            "score": score,
            "accessible": plan_satisfies(user_plan, defn.plan_required),
            "plan_required": defn.plan_required,
            "capabilities_matched": [
                c.value for c in needed if c in defn.capabilities
            ],
        }
        for defn, score in ranked
    ]


@router.get("/health/breakers")
async def circuit_breaker_health(
    user: Annotated[UserContext, Depends(get_current_user)],
) -> list[dict[str, Any]]:
    """Return circuit breaker status for all LLM providers.

    Requires authentication (at minimum). Useful for admin dashboards
    and incident response.
    """
    return get_all_breaker_metrics()
