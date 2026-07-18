"""Orchestrator SuperGraph — decomposes complex queries and coordinates agents.

Entry points:
- compile_orchestrator(): returns the compiled SuperGraph
- run_orchestrator(): one-shot invocation returning final merged result
- stream_orchestrator(): async generator yielding SSE events (in routers/orchestrate.py)
"""

from app.orchestration.orchestrator.graph import compile_orchestrator, run_orchestrator

__all__ = ["compile_orchestrator", "run_orchestrator"]
