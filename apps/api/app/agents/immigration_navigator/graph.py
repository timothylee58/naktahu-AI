"""Immigration Navigator LangGraph — multi-turn intake + immigration RAG,
plus the named-e-service reference-generation and SPO enquiry-drafting
tracks added alongside it (see nodes.py's module docstring for why those
generate copy-paste references instead of submitting anything).

    START -> service_router
      -> (SPO keywords)              -> spo_intake -> spo_output -> END
      -> (named e-service keywords)  -> service_intake -> service_output -> END
      -> (neither — original path)   -> intake -> immigration_rag -> output -> END

The original path's own nodes/edges are byte-for-byte unchanged from
before this addition — service_router only ever routes INTO it, never
alters its behaviour.
"""
from __future__ import annotations

from typing import Any, Optional

from langgraph.graph import END, START, StateGraph

from app.agents.checkpointer import get_checkpointer
from app.agents.immigration_navigator.nodes import (
    immigration_rag_node,
    intake_node,
    output_node,
    route_after_intake,
    route_after_service_detection,
    route_after_service_intake,
    route_after_spo_intake,
    service_intake_node,
    service_output_node,
    service_router_node,
    spo_intake_node,
    spo_output_node,
)
from app.agents.immigration_navigator.state import ImmigrationState

_compiled: Any = None


def build_immigration_navigator_graph() -> StateGraph:
    graph = StateGraph(ImmigrationState)
    graph.add_node("service_router", service_router_node)
    graph.add_node("intake", intake_node)
    graph.add_node("immigration_rag", immigration_rag_node)
    graph.add_node("output", output_node)
    graph.add_node("service_intake", service_intake_node)
    graph.add_node("service_output", service_output_node)
    graph.add_node("spo_intake", spo_intake_node)
    graph.add_node("spo_output", spo_output_node)

    graph.add_edge(START, "service_router")
    graph.add_conditional_edges(
        "service_router",
        route_after_service_detection,
        {"intake": "intake", "service_intake": "service_intake", "spo_intake": "spo_intake"},
    )

    graph.add_conditional_edges("intake", route_after_intake, {"immigration_rag": "immigration_rag", "__end__": END})
    graph.add_edge("immigration_rag", "output")
    graph.add_edge("output", END)

    graph.add_conditional_edges("service_intake", route_after_service_intake, {"service_output": "service_output", "__end__": END})
    graph.add_edge("service_output", END)

    graph.add_conditional_edges("spo_intake", route_after_spo_intake, {"spo_output": "spo_output", "__end__": END})
    graph.add_edge("spo_output", END)
    return graph


def get_immigration_navigator_graph(*, checkpointer: Optional[Any] = None):
    global _compiled
    cp = checkpointer if checkpointer is not None else get_checkpointer()
    if _compiled is None or checkpointer is not None:
        _compiled = build_immigration_navigator_graph().compile(checkpointer=cp)
    return _compiled
