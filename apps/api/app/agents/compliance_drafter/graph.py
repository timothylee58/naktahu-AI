"""Compliance Drafter LangGraph — multi-domain RAG report with HITL before PDF."""
from __future__ import annotations

from typing import Any, Optional

from langgraph.graph import END, START, StateGraph

from app.agents.checkpointer import get_checkpointer
from app.agents.compliance_drafter.nodes import (
    compile_node,
    generate_pdf_node,
    intake_node,
    notify_node,
    query_business_node,
    query_epf_node,
    query_tax_node,
)
from app.agents.compliance_drafter.state import ComplianceDrafterState

_compiled: Any = None


def build_compliance_drafter_graph() -> StateGraph:
    graph = StateGraph(ComplianceDrafterState)
    graph.add_node("intake", intake_node)
    graph.add_node("query_tax", query_tax_node)
    graph.add_node("query_business", query_business_node)
    graph.add_node("query_epf", query_epf_node)
    graph.add_node("compile", compile_node)
    graph.add_node("generate_pdf", generate_pdf_node)
    graph.add_node("notify", notify_node)

    graph.add_edge(START, "intake")
    graph.add_edge("intake", "query_tax")
    graph.add_edge("query_tax", "query_business")
    graph.add_edge("query_business", "query_epf")
    graph.add_edge("query_epf", "compile")
    graph.add_edge("compile", "generate_pdf")
    graph.add_edge("generate_pdf", "notify")
    graph.add_edge("notify", END)
    return graph


def get_compliance_drafter_graph(*, checkpointer: Optional[Any] = None):
    global _compiled
    cp = checkpointer if checkpointer is not None else get_checkpointer()
    if _compiled is None or checkpointer is not None:
        _compiled = build_compliance_drafter_graph().compile(
            checkpointer=cp,
            interrupt_before=["generate_pdf"],
        )
    return _compiled
