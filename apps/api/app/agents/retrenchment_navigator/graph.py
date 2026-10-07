"""Retrenchment Navigator LangGraph — multi-turn intake + legal/epf RAG + statutory-benefit output."""
from __future__ import annotations

from typing import Any, Optional

from langgraph.graph import END, START, StateGraph

from app.agents.checkpointer import get_checkpointer
from app.agents.retrenchment_navigator.nodes import (
    intake_node,
    output_node,
    retrenchment_rag_node,
    route_after_intake,
)
from app.agents.retrenchment_navigator.state import RetrenchmentState

_compiled: Any = None


def build_retrenchment_navigator_graph() -> StateGraph:
    graph = StateGraph(RetrenchmentState)
    graph.add_node("intake", intake_node)
    graph.add_node("retrenchment_rag", retrenchment_rag_node)
    graph.add_node("output", output_node)
    graph.add_edge(START, "intake")
    graph.add_conditional_edges("intake", route_after_intake, {"retrenchment_rag": "retrenchment_rag", "__end__": END})
    graph.add_edge("retrenchment_rag", "output")
    graph.add_edge("output", END)
    return graph


def get_retrenchment_navigator_graph(*, checkpointer: Optional[Any] = None):
    global _compiled
    cp = checkpointer if checkpointer is not None else get_checkpointer()
    if _compiled is None or checkpointer is not None:
        _compiled = build_retrenchment_navigator_graph().compile(checkpointer=cp)
    return _compiled
