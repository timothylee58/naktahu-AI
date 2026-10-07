"""Grant Draft Generator LangGraph — grant+profile draft with HITL before export."""
from __future__ import annotations

from typing import Any, Optional

from langgraph.graph import END, START, StateGraph

from app.agents.checkpointer import get_checkpointer
from app.agents.grant_draft_generator.nodes import (
    compile_node,
    draft_node,
    fetch_grant_node,
    generate_export_node,
    intake_node,
    notify_node,
)
from app.agents.grant_draft_generator.state import GrantDraftState

_compiled: Any = None


def build_grant_draft_generator_graph() -> StateGraph:
    graph = StateGraph(GrantDraftState)
    graph.add_node("intake", intake_node)
    graph.add_node("fetch_grant", fetch_grant_node)
    graph.add_node("draft", draft_node)
    graph.add_node("compile", compile_node)
    graph.add_node("generate_export", generate_export_node)
    graph.add_node("notify", notify_node)

    graph.add_edge(START, "intake")
    graph.add_edge("intake", "fetch_grant")
    graph.add_edge("fetch_grant", "draft")
    graph.add_edge("draft", "compile")
    graph.add_edge("compile", "generate_export")
    graph.add_edge("generate_export", "notify")
    graph.add_edge("notify", END)
    return graph


def get_grant_draft_generator_graph(*, checkpointer: Optional[Any] = None):
    global _compiled
    cp = checkpointer if checkpointer is not None else get_checkpointer()
    if _compiled is None or checkpointer is not None:
        _compiled = build_grant_draft_generator_graph().compile(
            checkpointer=cp,
            interrupt_before=["generate_export"],
        )
    return _compiled
