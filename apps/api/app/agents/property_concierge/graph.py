"""Property Concierge LangGraph — multi-turn intake + property RAG + lead-tier output."""
from __future__ import annotations

from typing import Any, Optional

from langgraph.graph import END, START, StateGraph

from app.agents.checkpointer import get_checkpointer
from app.agents.property_concierge.nodes import (
    intake_node,
    output_node,
    property_rag_node,
    route_after_intake,
)
from app.agents.property_concierge.state import PropertyConciergeState

_compiled: Any = None


def build_property_concierge_graph() -> StateGraph:
    graph = StateGraph(PropertyConciergeState)
    graph.add_node("intake", intake_node)
    graph.add_node("property_rag", property_rag_node)
    graph.add_node("output", output_node)
    graph.add_edge(START, "intake")
    graph.add_conditional_edges("intake", route_after_intake, {"property_rag": "property_rag", "__end__": END})
    graph.add_edge("property_rag", "output")
    graph.add_edge("output", END)
    return graph


def get_property_concierge_graph(*, checkpointer: Optional[Any] = None):
    global _compiled
    cp = checkpointer if checkpointer is not None else get_checkpointer()
    if _compiled is None or checkpointer is not None:
        _compiled = build_property_concierge_graph().compile(checkpointer=cp)
    return _compiled
