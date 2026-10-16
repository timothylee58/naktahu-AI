#!/usr/bin/env python3
"""Run apps/api/scripts/nemotron_check.py from the repository root.

The real script lives with the API because it imports the API's settings, and those
read apps/api/.env relative to the working directory. This wrapper switches to
apps/api first, so both of these work and use the same .env:

    python scripts/nemotron_check.py                  # from the repo root
    cd apps/api && python scripts/nemotron_check.py   # from apps/api
"""
from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path

_API_ROOT = Path(__file__).resolve().parents[1] / "apps" / "api"

if __name__ == "__main__":
    os.chdir(_API_ROOT)
    sys.argv[0] = str(_API_ROOT / "scripts" / "nemotron_check.py")
    runpy.run_path(sys.argv[0], run_name="__main__")
