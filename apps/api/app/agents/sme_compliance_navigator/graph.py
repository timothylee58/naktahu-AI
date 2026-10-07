"""SME Compliance Navigator (PatuhiKu) — router -> Send() fan-out -> synthesizer."""
from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from app.agents.sme_compliance_navigator.nodes import (
    route_to_subagents,
    router_node,
    subagent_node,
    synthesizer_node,
)
from app.agents.sme_compliance_navigator.state import ComplianceNavigatorState


def build_sme_compliance_navigator_graph() -> StateGraph:
    graph = StateGraph(ComplianceNavigatorState)
    graph.add_node("router_node", router_node)
    graph.add_node("subagent_node", subagent_node)
    graph.add_node("synthesizer_node", synthesizer_node)

    graph.add_edge(START, "router_node")
    graph.add_conditional_edges("router_node", route_to_subagents, ["subagent_node"])
    graph.add_edge("subagent_node", "synthesizer_node")
    graph.add_edge("synthesizer_node", END)
    return graph


_compiled: Any = None


def get_sme_compliance_navigator_graph():
    global _compiled
    if _compiled is None:
        _compiled = build_sme_compliance_navigator_graph().compile()
    return _compiled
