"""Enhanced agent registry — versioned definitions with capability vectors.

Replaces the flat services/agent_registry.py with a richer model that the
orchestrator uses for intelligent agent selection. Backwards-compatible:
the existing HTTP endpoints still work via get_agent() / list_agents(),
and the fallback registry provides the same agents as before.

New fields over the original AgentDefinition:
- version: semantic version string for code/state compatibility checks
- capabilities: list of AgentCapability enums (what it can do)
- supported_domains: RAG domains it can query
- supports_multi_turn: whether it has a continue_session flow
- supports_streaming: whether it yields tokens
- max_timeout_seconds: per-agent timeout budget
- input_schema / output_schema: JSON Schema dicts for validation
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import structlog
from supabase import Client

from app.orchestration.protocol import AgentProtocol
from app.orchestration.types import AgentCapability

log = structlog.get_logger(__name__)


@dataclass(frozen=True)
class EnhancedAgentDefinition:
    """Rich agent definition with capabilities, versioning, and schemas."""

    name: str
    version: str
    description: str
    capabilities: list[AgentCapability]
    supported_domains: list[str]
    plan_required: str = "free"
    credit_cost: int = 0
    supports_multi_turn: bool = False
    supports_streaming: bool = False
    max_timeout_seconds: float = 30.0
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)
    # Operational metadata
    enabled: bool = True
    deprecated: bool = False
    successor: Optional[str] = None  # agent name that replaces this one


# Ordinal rank for plan checks (same as services/agent_registry.py)
_PLAN_RANK = {"free": 0, "student": 1, "pro": 2, "business": 3}

# In-memory caches populated at startup.
_REGISTRY: dict[str, EnhancedAgentDefinition] = {}
_ADAPTERS: dict[str, AgentProtocol] = {}


def _fallback_registry() -> dict[str, EnhancedAgentDefinition]:
    """Built-in defaults when Supabase is unavailable (dev/tests).

    These mirror the original services/agent_registry.py fallback but with
    the richer capability model.
    """
    return {
        "compliance-drafter": EnhancedAgentDefinition(
            name="compliance-drafter",
            version="1.0.0",
            description="Multi-domain PDF compliance report for Malaysian businesses.",
            capabilities=[
                AgentCapability.compliance_analysis,
                AgentCapability.tax_knowledge,
                AgentCapability.business_knowledge,
                AgentCapability.epf_knowledge,
                AgentCapability.pdf_generation,
                AgentCapability.multi_domain_rag,
                AgentCapability.human_in_the_loop,
                AgentCapability.multi_turn,
            ],
            supported_domains=["tax", "business", "epf"],
            plan_required="free",
            credit_cost=1,
            supports_multi_turn=True,
            supports_streaming=False,
            max_timeout_seconds=60.0,
        ),
        "deadline-monitor": EnhancedAgentDefinition(
            name="deadline-monitor",
            version="1.0.0",
            description="Regulatory deadline calendar for Malaysian businesses.",
            capabilities=[
                AgentCapability.deadline_tracking,
                AgentCapability.tax_knowledge,
                AgentCapability.business_knowledge,
                AgentCapability.single_shot,
            ],
            supported_domains=["tax", "business", "epf"],
            plan_required="pro",
            credit_cost=0,
            supports_multi_turn=False,
            supports_streaming=False,
            max_timeout_seconds=10.0,
        ),
        "research-synthesiser": EnhancedAgentDefinition(
            name="research-synthesiser",
            version="1.0.0",
            description="Parallel multi-domain RAG synthesis across government, finance, and legal.",
            capabilities=[
                AgentCapability.multi_domain_rag,
                AgentCapability.government_knowledge,
                AgentCapability.finance_knowledge,
                AgentCapability.legal_knowledge,
                AgentCapability.education_knowledge,
                AgentCapability.single_shot,
            ],
            supported_domains=["government", "finance", "legal", "education"],
            plan_required="business",
            credit_cost=0,
            supports_multi_turn=False,
            supports_streaming=False,
            max_timeout_seconds=45.0,
        ),
        "sme-compliance-navigator": EnhancedAgentDefinition(
            name="sme-compliance-navigator",
            version="1.0.0",
            description="PatuhiKu — cross-references LHDN, EPF/SOCSO/EIS, and SSM compliance obligations for a specific SME.",
            capabilities=[
                AgentCapability.compliance_analysis,
                AgentCapability.tax_knowledge,
                AgentCapability.payroll_knowledge,
                AgentCapability.business_knowledge,
                AgentCapability.deadline_tracking,
                AgentCapability.multi_domain_rag,
                AgentCapability.single_shot,
            ],
            supported_domains=["tax", "payroll", "corporate"],
            plan_required="free",
            credit_cost=1,
        ),
        "welfare-eligibility-agent": EnhancedAgentDefinition(
            name="welfare-eligibility-agent",
            version="1.0.0",
            description="Matches a household profile against cost-of-living / social assistance schemes (Ihsan MADANI and similar).",
            capabilities=[
                AgentCapability.welfare_knowledge,
                AgentCapability.welfare_matching,
                AgentCapability.single_shot,
            ],
            supported_domains=["welfare"],
            plan_required="free",
            credit_cost=0,
            supports_multi_turn=False,
            supports_streaming=False,
            max_timeout_seconds=30.0,
        ),
        "study-agent": EnhancedAgentDefinition(
            name="study-agent",
            version="1.0.0",
            description="SPM past-paper upload with education RAG explanations.",
            capabilities=[
                AgentCapability.study_assistance,
                AgentCapability.education_knowledge,
                AgentCapability.document_processing,
                AgentCapability.multi_turn,
            ],
            supported_domains=["education"],
            plan_required="student",
            credit_cost=0,
            supports_multi_turn=True,
            supports_streaming=False,
            max_timeout_seconds=30.0,
        ),
        "immigration-navigator": EnhancedAgentDefinition(
            name="immigration-navigator",
            version="1.0.0",
            description="Conversational visa intake with immigration RAG.",
            capabilities=[
                AgentCapability.immigration_knowledge,
                AgentCapability.conversational_intake,
                AgentCapability.multi_turn,
            ],
            supported_domains=["immigration"],
            plan_required="free",
            credit_cost=1,
            supports_multi_turn=True,
            supports_streaming=False,
            max_timeout_seconds=30.0,
        ),
        "health-triage": EnhancedAgentDefinition(
            name="health-triage",
            version="1.0.0",
            description="BM symptom intake with KKM facility recommendations.",
            capabilities=[
                AgentCapability.symptom_triage,
                AgentCapability.healthcare_knowledge,
                AgentCapability.conversational_intake,
                AgentCapability.multi_turn,
            ],
            supported_domains=["healthcare"],
            plan_required="free",
            credit_cost=0,
            supports_multi_turn=True,
            supports_streaming=False,
            max_timeout_seconds=20.0,
        ),
        "eligibility-agent": EnhancedAgentDefinition(
            name="eligibility-agent",
            version="1.0.0",
            description="Multi-turn business grant-eligibility matching with scoring, near-miss detection, and stacking analysis.",
            capabilities=[
                AgentCapability.grant_matching,
                AgentCapability.government_knowledge,
                AgentCapability.finance_knowledge,
                AgentCapability.conversational_intake,
                AgentCapability.multi_turn,
            ],
            supported_domains=["government", "finance", "education"],
            plan_required="free",
            credit_cost=0,
            supports_multi_turn=True,
            supports_streaming=True,
            max_timeout_seconds=30.0,
        ),
        "knowledge-qa": EnhancedAgentDefinition(
            name="knowledge-qa",
            version="1.0.0",
            description="General Malaysian civic knowledge Q&A (the main RAG pipeline).",
            capabilities=[
                AgentCapability.government_knowledge,
                AgentCapability.education_knowledge,
                AgentCapability.legal_knowledge,
                AgentCapability.finance_knowledge,
                AgentCapability.healthcare_knowledge,
                AgentCapability.tax_knowledge,
                AgentCapability.epf_knowledge,
                AgentCapability.business_knowledge,
                AgentCapability.immigration_knowledge,
                AgentCapability.culture_knowledge,
                AgentCapability.streaming,
                AgentCapability.single_shot,
            ],
            supported_domains=[
                "government", "education", "legal", "finance",
                "healthcare", "epf", "tax", "business", "immigration", "culture",
            ],
            plan_required="free",
            credit_cost=0,
            supports_multi_turn=False,
            supports_streaming=True,
            max_timeout_seconds=30.0,
        ),
        "retrenchment-navigator": EnhancedAgentDefinition(
            name="retrenchment-navigator",
            version="1.0.0",
            description="Guided retrenchment options: EIS claim eligibility, statutory termination benefits, and next-steps checklist.",
            capabilities=[
                AgentCapability.legal_knowledge,
                AgentCapability.epf_knowledge,
                AgentCapability.conversational_intake,
                AgentCapability.multi_turn,
            ],
            supported_domains=["legal", "epf"],
            plan_required="free",
            credit_cost=0,
            supports_multi_turn=True,
            supports_streaming=False,
            max_timeout_seconds=30.0,
        ),
    }


def load_enhanced_registry(supabase_client: Optional[Client]) -> dict[str, EnhancedAgentDefinition]:
    """Load agent definitions from the agents table, enriched with capabilities.

    Falls back to built-in defaults if Supabase is unavailable. The DB
    table may have the new columns (version, capabilities, supported_domains)
    or not — we handle both gracefully.
    """
    global _REGISTRY

    if not supabase_client:
        _REGISTRY = _fallback_registry()
        log.warning("orchestration_registry_fallback", count=len(_REGISTRY))
        return _REGISTRY

    try:
        res = supabase_client.table("agents").select("*").execute()
        rows = res.data or []
    except Exception as exc:
        log.warning("orchestration_registry_load_failed", error=str(exc))
        _REGISTRY = _fallback_registry()
        return _REGISTRY

    # Merge DB rows with fallback definitions (DB overrides name/plan/cost,
    # but capabilities come from the fallback until the DB has the columns).
    fallback = _fallback_registry()
    loaded: dict[str, EnhancedAgentDefinition] = {}

    for row in rows:
        name = row.get("name", "")
        if not name:
            continue

        # If we have a rich fallback definition, use its capabilities/domains
        # as the base and override with any DB-provided values.
        base = fallback.get(name)

        # Parse capabilities from DB if present (stored as list of strings)
        raw_caps = row.get("capabilities") or []
        capabilities = []
        for cap_str in raw_caps:
            try:
                capabilities.append(AgentCapability(cap_str))
            except ValueError:
                pass
        if not capabilities and base:
            capabilities = base.capabilities

        # Parse supported_domains from DB if present
        supported_domains = row.get("supported_domains") or []
        if not supported_domains and base:
            supported_domains = base.supported_domains

        loaded[name] = EnhancedAgentDefinition(
            name=name,
            version=row.get("version") or (base.version if base else "0.1.0"),
            description=row.get("description") or (base.description if base else ""),
            capabilities=capabilities,
            supported_domains=supported_domains,
            plan_required=row.get("plan_required") or (base.plan_required if base else "free"),
            credit_cost=int(row.get("credit_cost") or (base.credit_cost if base else 0)),
            supports_multi_turn=row.get("supports_multi_turn") if row.get("supports_multi_turn") is not None else (base.supports_multi_turn if base else False),
            supports_streaming=row.get("supports_streaming") if row.get("supports_streaming") is not None else (base.supports_streaming if base else False),
            max_timeout_seconds=float(row.get("max_timeout_seconds") or (base.max_timeout_seconds if base else 30.0)),
            input_schema=row.get("input_schema") or (base.input_schema if base else {}),
            output_schema=row.get("output_schema") or (base.output_schema if base else {}),
            enabled=row.get("enabled", True),
            deprecated=row.get("deprecated", False),
            successor=row.get("successor"),
        )

    # Add any fallback agents not present in the DB (e.g., knowledge-qa
    # which is a virtual agent wrapping the main pipeline, not stored in DB)
    for name, defn in fallback.items():
        if name not in loaded:
            loaded[name] = defn

    _REGISTRY = loaded
    log.info("orchestration_registry_loaded", count=len(_REGISTRY))
    return _REGISTRY


def register_adapter(adapter: AgentProtocol) -> None:
    """Register a live AgentProtocol adapter for runtime invocation.

    Called during app startup after adapters are instantiated. The orchestrator
    uses these to actually invoke agents.
    """
    _ADAPTERS[adapter.name] = adapter
    log.info("adapter_registered", agent=adapter.name, version=adapter.version)


def get_adapter(name: str) -> Optional[AgentProtocol]:
    """Get the live adapter for an agent by name."""
    return _ADAPTERS.get(name)


def get_definition(name: str) -> Optional[EnhancedAgentDefinition]:
    """Get the agent definition (metadata) by name."""
    return _REGISTRY.get(name)


def list_definitions() -> list[EnhancedAgentDefinition]:
    """List all registered agent definitions."""
    return [d for d in _REGISTRY.values() if d.enabled]


def list_adapters() -> list[AgentProtocol]:
    """List all registered live adapters."""
    return list(_ADAPTERS.values())


def find_agents_for_domain(domain: str) -> list[EnhancedAgentDefinition]:
    """Find all agents that support a given domain."""
    return [d for d in _REGISTRY.values() if d.enabled and domain in d.supported_domains]


def find_agents_by_capability(capability: AgentCapability) -> list[EnhancedAgentDefinition]:
    """Find all agents with a specific capability."""
    return [d for d in _REGISTRY.values() if d.enabled and capability in d.capabilities]


def plan_satisfies(user_plan: str, required: str) -> bool:
    """Check if user_plan meets or exceeds the required plan tier."""
    return _PLAN_RANK.get(user_plan, 0) >= _PLAN_RANK.get(required, 0)


def get_best_agents_for_task(
    domain: str,
    capabilities_needed: list[AgentCapability],
    user_plan: str = "free",
    limit: int = 3,
) -> list[tuple[EnhancedAgentDefinition, float]]:
    """Rank agents by fitness for a task. Returns (definition, score) pairs.

    Used by the orchestrator's planner to select which agent(s) to invoke
    for a decomposed sub-task.

    Scoring:
    - Domain match: +0.4 per matching domain
    - Capability coverage: +0.6 * (matched / total needed)
    - Plan-accessible bonus: +0.1 (so we prefer accessible agents when tied)
    """
    candidates: list[tuple[EnhancedAgentDefinition, float]] = []

    for defn in _REGISTRY.values():
        if not defn.enabled or defn.deprecated:
            continue

        score = 0.0

        # Domain match (0.4 max)
        if domain in defn.supported_domains:
            score += 0.4

        # Capability coverage (0.6 max)
        if capabilities_needed:
            matched = sum(1 for c in capabilities_needed if c in defn.capabilities)
            score += 0.6 * (matched / len(capabilities_needed))

        # Plan-accessible bonus
        if plan_satisfies(user_plan, defn.plan_required):
            score += 0.1

        if score > 0.0:
            candidates.append((defn, round(score, 4)))

    candidates.sort(key=lambda pair: pair[1], reverse=True)
    return candidates[:limit]
