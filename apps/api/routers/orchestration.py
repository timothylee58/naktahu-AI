"""Orchestration router — re-exports from app.routers.orchestration.

This file exists so the root main.py (used by the test suite) can mount
the orchestration endpoints alongside the deploy-only app/main.py.
See CLAUDE.md Trap #1 for why both mains need every router.
"""
from app.routers.orchestration import router  # noqa: F401

__all__ = ["router"]
