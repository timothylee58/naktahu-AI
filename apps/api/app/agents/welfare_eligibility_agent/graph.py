"""Welfare Eligibility Agent LangGraph — single-shot match -> synthesiser.

No checkpointer: unlike eligibility_agent (multi-turn business-grant
intake), this agent takes one complete 14-field profile and returns one
result, the same single-shot shape as sme_compliance_navigator.
"""
from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from app.agents.runtime import supabase_from_config
from app.agents.welfare_eligibility_agent.match_node import match_node
from app.agents.welfare_eligibility_agent.state import WelfareState
from app.agents.welfare_eligibility_agent.synthesiser_node import synthesiser_node

_compiled: Any = None


async def _match_node(state: WelfareState, config: RunnableConfig | None = None) -> dict[str, Any]:
    return await match_node(state, supabase_from_config(config))


def build_welfare_eligibility_agent_graph() -> StateGraph:
    graph = StateGraph(WelfareState)
    graph.add_node("match", _match_node)
    graph.add_node("synthesiser", synthesiser_node)
    graph.add_edge(START, "match")
    graph.add_edge("match", "synthesiser")
    graph.add_edge("synthesiser", END)
    return graph


def get_welfare_eligibility_agent_graph():
    global _compiled
    if _compiled is None:
        _compiled = build_welfare_eligibility_agent_graph().compile()
    return _compiled
