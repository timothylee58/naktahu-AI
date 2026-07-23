"""planner_node — LLM-powered query decomposition into sub-tasks.

Analyzes query complexity and decides:
- SIMPLE: single-domain factual question → fast-path to knowledge-qa
- MODERATE: requires one specific vertical agent (grant-finder, health-triage, etc.)
- COMPLEX: multi-domain or multi-step → decomposes into parallel/sequential sub-tasks

The planner uses ILMU chat with structured JSON output. On failure it falls
back to a heuristic keyword-based classifier (never blocks the pipeline).
"""
from __future__ import annotations

import json
import re
import uuid
from typing import Any

import structlog

from app.orchestration.orchestrator.state import OrchestratorState, SubTaskState
from app.services.llm_client import ILMU_CHAT_MODEL, ilmu_client

log = structlog.get_logger(__name__)

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)

_PLANNER_SYSTEM_PROMPT = """\
You are a query planner for NakTahu AI, a Malaysian civic knowledge system.

Given a user query, analyze its complexity and decompose it if needed.

DOMAINS: government, education, legal, finance, healthcare, epf, tax, business, immigration, culture

AGENTS AVAILABLE:
- knowledge-qa: General factual Q&A about Malaysian public services (any domain)
- compliance-drafter: Multi-domain compliance reports for businesses (tax, business, epf)
- grant-finder: Government grant matching for SMEs and students
- health-triage: Symptom intake with KKM facility recommendations
- immigration-navigator: Visa/immigration guidance with conversational intake
- study-agent: SPM exam prep with education RAG
- research-synthesiser: Parallel multi-domain research synthesis
- sme-compliance-navigator: PatuhiKu — cross-references LHDN/EPF-SOCSO-EIS/SSM obligations for a specific SME

COMPLEXITY RULES:
- SIMPLE: Single factual question about one domain. Example: "What is EPF withdrawal age?"
- MODERATE: Needs a specific vertical agent. Example: "I have a headache, where should I go?"
- COMPLEX: Spans multiple domains OR requires multiple agents. Example: "I want to start a business in Malaysia - what grants, tax obligations, and SSM registration steps apply?"

Return JSON only:
{
  "complexity": "simple" | "moderate" | "complex",
  "reasoning": "brief explanation",
  "sub_tasks": [
    {
      "description": "what this sub-task answers",
      "domain": "primary domain",
      "capabilities_needed": ["capability1", "capability2"],
      "depends_on": []
    }
  ]
}

For SIMPLE queries: return exactly 1 sub-task with domain and empty capabilities_needed.
For MODERATE queries: return 1 sub-task with specific capabilities (e.g. ["grant_matching"]).
For COMPLEX queries: return 2-4 sub-tasks. Use depends_on (by index, 0-based) when one task needs another's output.
"""

# ── Heuristic fallback (no LLM required) ──────────────────────────────────────

_AGENT_KEYWORDS: dict[str, tuple[list[str], list[str]]] = {
    # agent_name: (keywords, capabilities)
    "health-triage": (
        ["symptom", "sakit", "doctor", "doktor", "klinik", "hospital", "demam", "batuk", "pening"],
        ["symptom_triage", "healthcare_knowledge"],
    ),
    "immigration-navigator": (
        ["visa", "pasport", "passport", "immigration", "imigresen", "work permit", "pas kerja"],
        ["immigration_knowledge", "conversational_intake"],
    ),
    "grant-finder": (
        ["grant", "geran", "funding", "bantuan", "subsidi", "pinjaman perniagaan"],
        ["grant_matching", "government_knowledge"],
    ),
    "study-agent": (
        ["spm", "exam", "peperiksaan", "study", "belajar", "past paper", "kertas soalan"],
        ["study_assistance", "education_knowledge"],
    ),
    "compliance-drafter": (
        ["compliance", "pematuhan", "report", "laporan", "ssm registration", "daftar syarikat"],
        ["compliance_analysis", "tax_knowledge", "business_knowledge"],
    ),
    "research-synthesiser": (
        ["research", "compare", "banding", "comprehensive", "menyeluruh", "all aspects"],
        ["multi_domain_rag"],
    ),
    "sme-compliance-navigator": (
        ["patuhiku", "sme compliance", "compliance checklist", "sdn bhd", "epf socso",
         "e-invoice", "annual return", "senarai semak pematuhan"],
        ["compliance_analysis", "tax_knowledge", "payroll_knowledge", "business_knowledge"],
    ),
}

_MULTI_DOMAIN_INDICATORS = [
    "and also", "dan juga", "together with", "bersama",
    "what about", "bagaimana pula", "in addition", "selain itu",
    "start a business", "buka perniagaan", "move to malaysia", "pindah ke malaysia",
]

_DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "tax": ["tax", "cukai", "lhdn", "sst", "income tax"],
    "epf": ["epf", "kwsp", "caruman", "withdrawal", "pengeluaran"],
    "business": ["ssm", "business", "perniagaan", "company", "syarikat"],
    "immigration": ["visa", "passport", "pasport", "immigration", "imigresen"],
    "healthcare": ["health", "hospital", "klinik", "doctor", "kkm", "sakit"],
    "education": ["education", "pendidikan", "spm", "university", "universiti"],
    "finance": ["bank", "loan", "pinjaman", "investment", "pelaburan"],
    "legal": ["law", "undang", "court", "mahkamah", "legal"],
    "government": ["government", "kerajaan", "jabatan", "kementerian"],
    "culture": ["culture", "budaya", "heritage", "warisan"],
}


def _detect_domains(query: str) -> list[str]:
    """Detect which domains a query touches."""
    lower = query.lower()
    domains: list[str] = []
    for domain, keywords in _DOMAIN_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            domains.append(domain)
    return domains or ["government"]


def _detect_target_agent(query: str) -> tuple[str | None, list[str]]:
    """Try to match query to a specific vertical agent via keywords."""
    lower = query.lower()
    for agent_name, (keywords, capabilities) in _AGENT_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            return agent_name, capabilities
    return None, []


def _is_multi_domain(query: str) -> bool:
    """Heuristic: does the query span multiple domains or ask for compound info?"""
    lower = query.lower()
    if any(indicator in lower for indicator in _MULTI_DOMAIN_INDICATORS):
        return True
    domains = _detect_domains(query)
    return len(domains) >= 2


def _heuristic_plan(query: str, language: str) -> dict[str, Any]:
    """Fallback planner when LLM is unavailable."""
    domains = _detect_domains(query)
    target_agent, capabilities = _detect_target_agent(query)

    if _is_multi_domain(query) and len(domains) >= 2:
        # COMPLEX: multi-domain
        sub_tasks = []
        for i, domain in enumerate(domains[:3]):
            sub_tasks.append({
                "description": f"Find information about {domain} aspects of the query",
                "domain": domain,
                "capabilities_needed": [f"{domain}_knowledge"],
                "depends_on": [],
            })
        return {
            "complexity": "complex",
            "reasoning": f"Query spans {len(domains)} domains: {', '.join(domains[:3])}",
            "sub_tasks": sub_tasks,
        }
    elif target_agent:
        # MODERATE: specific agent
        return {
            "complexity": "moderate",
            "reasoning": f"Query matches {target_agent} capabilities",
            "sub_tasks": [{
                "description": query,
                "domain": domains[0],
                "capabilities_needed": capabilities,
                "depends_on": [],
            }],
        }
    else:
        # SIMPLE: general knowledge
        return {
            "complexity": "simple",
            "reasoning": "Single-domain factual question",
            "sub_tasks": [{
                "description": query,
                "domain": domains[0],
                "capabilities_needed": [],
                "depends_on": [],
            }],
        }


# ── Main planner node ─────────────────────────────────────────────────────────


async def planner_node(state: OrchestratorState) -> dict[str, Any]:
    """Analyze query complexity and decompose into sub-tasks.

    Uses ILMU for intelligent decomposition. Falls back to keyword
    heuristics on any failure (never blocks the pipeline).
    """
    query = state.get("query", "")
    language = state.get("language", "en")

    # Try LLM-powered planning
    plan: dict[str, Any] | None = None
    try:
        resp = await ilmu_client.chat.completions.create(
            model=ILMU_CHAT_MODEL,
            messages=[
                {"role": "system", "content": _PLANNER_SYSTEM_PROMPT},
                {"role": "user", "content": f"Query (language={language}): {query}"},
            ],
            max_tokens=512,
            temperature=0,
        )
        raw = resp.choices[0].message.content or ""
        m = _JSON_RE.search(raw)
        if m:
            plan = json.loads(m.group(0))
    except Exception as exc:
        log.warning("planner_llm_failed_using_heuristic", error=str(exc), query=query[:80])

    # Fall back to heuristics if LLM failed or returned invalid structure
    if not plan or "complexity" not in plan or "sub_tasks" not in plan:
        plan = _heuristic_plan(query, language)

    # Normalize and validate the plan
    complexity = plan.get("complexity", "simple")
    if complexity not in ("simple", "moderate", "complex"):
        complexity = "simple"

    reasoning = plan.get("reasoning", "")
    raw_tasks = plan.get("sub_tasks", [])
    if not isinstance(raw_tasks, list) or not raw_tasks:
        raw_tasks = [{"description": query, "domain": "government", "capabilities_needed": [], "depends_on": []}]

    # Convert to SubTaskState with generated IDs
    sub_tasks: list[SubTaskState] = []
    task_ids: list[str] = []
    for i, raw in enumerate(raw_tasks[:4]):  # Cap at 4 sub-tasks
        task_id = f"task_{i}_{uuid.uuid4().hex[:8]}"
        task_ids.append(task_id)

        # Resolve depends_on from indices to task_ids
        raw_deps = raw.get("depends_on", [])
        deps: list[str] = []
        for dep in raw_deps:
            if isinstance(dep, int) and 0 <= dep < len(task_ids) - 1:
                deps.append(task_ids[dep])

        sub_tasks.append(SubTaskState(
            task_id=task_id,
            description=raw.get("description", query),
            target_agent="",  # assigned by router_node
            domain=raw.get("domain", "government"),
            capabilities_needed=raw.get("capabilities_needed", []),
            priority=i,
            depends_on=deps,
            status="pending",
            result=None,
        ))

    # Determine fast-path for simple queries
    fast_path_agent: str | None = None
    if complexity == "simple":
        fast_path_agent = "knowledge-qa"
    elif complexity == "moderate" and len(sub_tasks) == 1:
        # Check if heuristics already identified the agent
        target, _ = _detect_target_agent(query)
        if target:
            fast_path_agent = target

    log.info(
        "planner_done",
        complexity=complexity,
        sub_tasks=len(sub_tasks),
        fast_path=fast_path_agent,
        reasoning=reasoning[:100],
    )

    return {
        "complexity": complexity,
        "reasoning": reasoning,
        "sub_tasks": sub_tasks,
        "fast_path_agent": fast_path_agent,
    }
