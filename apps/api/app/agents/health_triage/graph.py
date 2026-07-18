"""Health Triage LangGraph — free civic KKM symptom tool."""
from __future__ import annotations

from typing import Any, Optional

from langgraph.graph import END, START, StateGraph

from app.agents.checkpointer import get_checkpointer
from app.agents.health_triage.nodes import disclaimer_node, facility_node, kkm_rag_node, symptom_intake_node
from app.agents.health_triage.state import HealthTriageState

_compiled: Any = None


def build_health_triage_graph() -> StateGraph:
    graph = StateGraph(HealthTriageState)
    graph.add_node("symptom_intake", symptom_intake_node)
    graph.add_node("kkm_rag", kkm_rag_node)
    graph.add_node("facility", facility_node)
    graph.add_node("disclaimer", disclaimer_node)
    graph.add_edge(START, "symptom_intake")
    graph.add_edge("symptom_intake", "kkm_rag")
    graph.add_edge("kkm_rag", "facility")
    graph.add_edge("facility", "disclaimer")
    graph.add_edge("disclaimer", END)
    return graph


def get_health_triage_graph(*, checkpointer: Optional[Any] = None):
    global _compiled
    cp = checkpointer if checkpointer is not None else get_checkpointer()
    if _compiled is None or checkpointer is not None:
        _compiled = build_health_triage_graph().compile(checkpointer=cp)
    return _compiled
