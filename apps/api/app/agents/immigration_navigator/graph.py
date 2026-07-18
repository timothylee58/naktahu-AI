"""Immigration Navigator LangGraph — multi-turn intake + immigration RAG."""
from __future__ import annotations

from typing import Any, Optional

from langgraph.graph import END, START, StateGraph

from app.agents.checkpointer import get_checkpointer
from app.agents.immigration_navigator.nodes import immigration_rag_node, intake_node, output_node, route_after_intake
from app.agents.immigration_navigator.state import ImmigrationState

_compiled: Any = None


def build_immigration_navigator_graph() -> StateGraph:
    graph = StateGraph(ImmigrationState)
    graph.add_node("intake", intake_node)
    graph.add_node("immigration_rag", immigration_rag_node)
    graph.add_node("output", output_node)
    graph.add_edge(START, "intake")
    graph.add_conditional_edges("intake", route_after_intake, {"immigration_rag": "immigration_rag", "__end__": END})
    graph.add_edge("immigration_rag", "output")
    graph.add_edge("output", END)
    return graph


def get_immigration_navigator_graph(*, checkpointer: Optional[Any] = None):
    global _compiled
    cp = checkpointer if checkpointer is not None else get_checkpointer()
    if _compiled is None or checkpointer is not None:
        _compiled = build_immigration_navigator_graph().compile(checkpointer=cp)
    return _compiled
