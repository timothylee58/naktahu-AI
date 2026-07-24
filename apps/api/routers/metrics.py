"""Metrics router — re-exports from app.routers.metrics.

This file exists so the root main.py (used by the test suite) can mount
the /metrics endpoint alongside the deploy-only app/main.py.
See CLAUDE.md Trap #1 for why both mains need every router.
"""
from app.routers.metrics import router  # noqa: F401

__all__ = ["router"]
