"""Research Synthesiser — parallel fan-out via LangGraph Send() API."""
from __future__ import annotations

import operator
from typing import Annotated, Any

import structlog
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send
from typing_extensions import TypedDict

from app.agents.tools import query_rag_findings

log = structlog.get_logger(__name__)

_MAX_DOMAINS = 3


class ResearchState(TypedDict, total=False):
    query: str
    language: str
    detected_domains: list[str]
    domain_results: Annotated[list[dict[str, Any]], operator.add]
    merged_citations: list[dict[str, Any]]
    citations: list[dict[str, Any]]


async def router_domains_node(state: ResearchState) -> dict[str, Any]:
    """Detect which RAG domains to fan out to (max 3)."""
    query = (state.get("query") or "").lower()
    domains: list[str] = []
    if any(k in query for k in ("cukai", "tax", "lhdn", "sst")):
        domains.append("finance")
    if any(k in query for k in ("ssm", "syarikat", "business", "company")):
        domains.append("government")
    if any(k in query for k in ("epf", "kwsp", "pendidikan", "spm", "education")):
        domains.append("education")
    if not domains:
        domains = ["government", "finance", "legal"]
    return {"detected_domains": domains[:_MAX_DOMAINS], "domain_results": []}


def route_to_domains(state: ResearchState) -> list[Send]:
    return [
        Send("rag_node", {"query": state.get("query", ""), "domain": d, "language": state.get("language", "bm")})
        for d in (state.get("detected_domains") or [])
    ]


async def rag_domain_node(state: dict[str, Any]) -> dict[str, Any]:
    domain = state.get("domain", "government")
    query = state.get("query", "")
    language = state.get("language", "bm")
    findings = await query_rag_findings(query, domain, language)
    return {"domain_results": [{"domain": domain, "findings": findings}]}


async def merge_node(state: ResearchState) -> dict[str, Any]:
    """Deduplicate citations across parallel domain results."""
    seen_urls: set[str] = set()
    merged: list[dict[str, Any]] = []
    for block in state.get("domain_results") or []:
        for f in block.get("findings") or []:
            url = f.get("source_url") or ""
            if url and url in seen_urls:
                continue
            if url:
                seen_urls.add(url)
            merged.append({
                "title": f.get("source_title", ""),
                "url": url,
                "ministry": f.get("domain", ""),
                "confidence": float(f.get("similarity", 0.0) if "similarity" in f else 0.7),
            })
    return {"merged_citations": merged[:9], "citations": merged[:9]}


def build_research_synthesiser_graph() -> StateGraph:
    graph = StateGraph(ResearchState)
    graph.add_node("router_node", router_domains_node)
    graph.add_node("rag_node", rag_domain_node)
    graph.add_node("merge_node", merge_node)

    graph.add_edge(START, "router_node")
    graph.add_conditional_edges("router_node", route_to_domains, ["rag_node"])
    graph.add_edge("rag_node", "merge_node")
    graph.add_edge("merge_node", END)
    return graph


_research_compiled: Any = None


def get_research_synthesiser_graph():
    global _research_compiled
    if _research_compiled is None:
        _research_compiled = build_research_synthesiser_graph().compile()
    return _research_compiled
