"""Product-agent registry — loaded from the agents table on API startup."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import structlog
from supabase import Client

log = structlog.get_logger(__name__)


@dataclass(frozen=True)
class AgentDefinition:
    name: str
    description: str
    input_schema: dict[str, Any]
    plan_required: str
    credit_cost: int


_PLAN_RANK = {"free": 0, "student": 1, "pro": 2, "business": 3}

# In-memory cache populated at startup.
_REGISTRY: dict[str, AgentDefinition] = {}


def _fallback_registry() -> dict[str, AgentDefinition]:
    """Built-in defaults when Supabase is unavailable (dev/tests)."""
    return {
        "compliance-drafter": AgentDefinition(
            name="compliance-drafter",
            description="Multi-domain PDF compliance report.",
            input_schema={},
            plan_required="free",
            credit_cost=1,
        ),
        "deadline-monitor": AgentDefinition(
            name="deadline-monitor",
            description="Regulatory deadline calendar.",
            input_schema={},
            plan_required="pro",
            credit_cost=0,
        ),
        "research-synthesiser": AgentDefinition(
            name="research-synthesiser",
            description="Parallel multi-domain RAG synthesis.",
            input_schema={},
            plan_required="business",
            credit_cost=0,
        ),
        "study-agent": AgentDefinition(
            name="study-agent",
            description="SPM past-paper upload with education RAG explanations.",
            input_schema={},
            plan_required="student",
            credit_cost=0,
        ),
        "immigration-navigator": AgentDefinition(
            name="immigration-navigator",
            description="Conversational visa intake with immigration RAG.",
            input_schema={},
            plan_required="free",
            credit_cost=1,
        ),
        "health-triage": AgentDefinition(
            name="health-triage",
            description="BM symptom intake with KKM facility recommendations.",
            input_schema={},
            plan_required="free",
            credit_cost=0,
        ),
        "eligibility-agent": AgentDefinition(
            name="eligibility-agent",
            description="Multi-turn business grant-eligibility matching with scoring, near-miss detection, and stacking analysis.",
            input_schema={},
            plan_required="free",
            credit_cost=0,
        ),
        "sme-compliance-navigator": AgentDefinition(
            name="sme-compliance-navigator",
            description="PatuhiKu — cross-references LHDN, EPF/SOCSO/EIS, and SSM compliance obligations for a specific SME.",
            input_schema={},
            plan_required="free",
            credit_cost=1,
        ),
        "grant-draft-generator": AgentDefinition(
            name="grant-draft-generator",
            description=(
                "Grant application draft: executive summary, use-of-funds narrative, "
                "financial projection skeleton, and required-document checklist for a "
                "selected grant + business profile. Export as PDF or Word (.docx)."
            ),
            input_schema={
                "programme_name": {"type": "string", "required": True},
                "business_profile": {"type": "object", "required": True},
                "export_format": {"type": "string", "enum": ["pdf", "docx"], "default": "pdf"},
            },
            plan_required="free",
            credit_cost=3,
        ),
    }


def load_agent_registry(supabase_client: Optional[Client]) -> dict[str, AgentDefinition]:
    global _REGISTRY
    if not supabase_client:
        _REGISTRY = _fallback_registry()
        log.warning("agent_registry_fallback", count=len(_REGISTRY))
        return _REGISTRY

    try:
        res = supabase_client.table("agents").select("*").execute()
        rows = res.data or []
        _REGISTRY = {
            row["name"]: AgentDefinition(
                name=row["name"],
                description=row.get("description") or "",
                input_schema=row.get("input_schema") or {},
                plan_required=row.get("plan_required") or "free",
                credit_cost=int(row.get("credit_cost") or 0),
            )
            for row in rows
        }
        log.info("agent_registry_loaded", count=len(_REGISTRY))
    except Exception as exc:
        log.warning("agent_registry_load_failed", error=str(exc))
        _REGISTRY = _fallback_registry()

    return _REGISTRY


def get_agent(name: str) -> Optional[AgentDefinition]:
    return _REGISTRY.get(name)


def list_agents() -> list[AgentDefinition]:
    return list(_REGISTRY.values())


def plan_satisfies(user_plan: str, required: str) -> bool:
    return _PLAN_RANK.get(user_plan, 0) >= _PLAN_RANK.get(required, 0)


_BUSINESS_UNLIMITED_AGENTS = frozenset({"compliance-drafter", "grant-draft-generator"})


def is_credit_exempt(user_plan: str, agent_name: str, *, role: Optional[str] = None) -> bool:
    """Business plan gets unlimited Compliance Drafter + Grant Draft Generator;
    admins are fully exempt."""
    from services.auth import is_admin_role

    if is_admin_role(role):
        return True
    return user_plan == "business" and agent_name in _BUSINESS_UNLIMITED_AGENTS
