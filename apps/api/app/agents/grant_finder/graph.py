"""Grant Finder LangGraph — government grant matching for SMEs & students."""
from __future__ import annotations

from typing import Any, Optional

from langgraph.graph import END, START, StateGraph

from app.agents.checkpointer import get_checkpointer
from app.agents.grant_finder.nodes import grant_rag_node, match_node, profile_node
from app.agents.grant_finder.state import GrantFinderState

_compiled: Any = None


def build_grant_finder_graph() -> StateGraph:
    graph = StateGraph(GrantFinderState)
    graph.add_node("profile", profile_node)
    graph.add_node("grant_rag", grant_rag_node)
    graph.add_node("match", match_node)
    graph.add_edge(START, "profile")
    graph.add_edge("profile", "grant_rag")
    graph.add_edge("grant_rag", "match")
    graph.add_edge("match", END)
    return graph


def get_grant_finder_graph(*, checkpointer: Optional[Any] = None):
    global _compiled
    cp = checkpointer if checkpointer is not None else get_checkpointer()
    if _compiled is None or checkpointer is not None:
        _compiled = build_grant_finder_graph().compile(checkpointer=cp)
    return _compiled
