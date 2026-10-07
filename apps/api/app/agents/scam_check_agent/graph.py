"""ScamShield LangGraph — single-shot check -> synthesiser.

No checkpointer: one pasted text in, one verdict out — same single-shot
shape as welfare_eligibility_agent, not eligibility_agent's multi-turn
intake.
"""
from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from app.agents.runtime import supabase_from_config
from app.agents.scam_check_agent.check_node import check_node
from app.agents.scam_check_agent.state import ScamCheckState
from app.agents.scam_check_agent.synthesiser_node import synthesiser_node

_compiled: Any = None


async def _check_node(state: ScamCheckState, config: RunnableConfig | None = None) -> dict[str, Any]:
    return await check_node(state, supabase_from_config(config))


def build_scam_check_agent_graph() -> StateGraph:
    graph = StateGraph(ScamCheckState)
    graph.add_node("check", _check_node)
    graph.add_node("synthesiser", synthesiser_node)
    graph.add_edge(START, "check")
    graph.add_edge("check", "synthesiser")
    graph.add_edge("synthesiser", END)
    return graph


def get_scam_check_agent_graph():
    global _compiled
    if _compiled is None:
        _compiled = build_scam_check_agent_graph().compile()
    return _compiled
