"""Observability router — re-exports from app.routers.observability.

This file exists so the root main.py (used by the test suite) can mount
the observability endpoints alongside the deploy-only app/main.py.
See CLAUDE.md Trap #1 for why both mains need every router.
"""
from app.routers.observability import router  # noqa: F401

__all__ = ["router"]
