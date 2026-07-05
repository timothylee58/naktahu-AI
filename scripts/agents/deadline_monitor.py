#!/usr/bin/env python3
"""Repo-root entrypoint — delegates to apps/api/scripts/agents/deadline_monitor.py."""
from __future__ import annotations

import runpy
import sys
from pathlib import Path

_API_SCRIPT = (
    Path(__file__).resolve().parents[2] / "apps" / "api" / "scripts" / "agents" / "deadline_monitor.py"
)
_API_ROOT = _API_SCRIPT.parents[2]

if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

runpy.run_path(str(_API_SCRIPT), run_name="__main__")
