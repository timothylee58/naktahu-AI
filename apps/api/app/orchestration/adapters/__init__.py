"""Agent adapters — bridge existing vertical agents to the AgentProtocol.

Each adapter wraps an existing LangGraph agent (or the main pipeline) so the
orchestrator can invoke it uniformly. Adapters don't modify agent internals;
they translate between OrchestratorContext and the agent's native input/output.
"""

from app.orchestration.adapters.compliance_drafter import ComplianceDrafterAdapter
from app.orchestration.adapters.eligibility_agent import EligibilityAgentAdapter
from app.orchestration.adapters.health_triage import HealthTriageAdapter
from app.orchestration.adapters.immigration_navigator import ImmigrationNavigatorAdapter
from app.orchestration.adapters.knowledge_qa import KnowledgeQAAdapter
from app.orchestration.adapters.research_synthesiser import ResearchSynthesiserAdapter
from app.orchestration.adapters.sme_compliance_navigator import SMEComplianceNavigatorAdapter
from app.orchestration.adapters.study_agent import StudyAgentAdapter

ALL_ADAPTERS = [
    ComplianceDrafterAdapter,
    EligibilityAgentAdapter,
    HealthTriageAdapter,
    ImmigrationNavigatorAdapter,
    KnowledgeQAAdapter,
    ResearchSynthesiserAdapter,
    SMEComplianceNavigatorAdapter,
    StudyAgentAdapter,
]

__all__ = [
    "ComplianceDrafterAdapter",
    "EligibilityAgentAdapter",
    "HealthTriageAdapter",
    "ImmigrationNavigatorAdapter",
    "KnowledgeQAAdapter",
    "ResearchSynthesiserAdapter",
    "SMEComplianceNavigatorAdapter",
    "StudyAgentAdapter",
    "ALL_ADAPTERS",
]
