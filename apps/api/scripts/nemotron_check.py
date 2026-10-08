#!/usr/bin/env python3
"""Check the Nemotron configuration against the live endpoint.

Model IDs for the Eligibility Agent's Nemotron split are never defaulted in code
because the sources that publish them disagree (casing, "nvidia/" prefix, newer
variants appear). This lists what the endpoint actually serves and makes one tiny
real request with each configured ID, so a wrong ID fails here, not in production.

    NEMOTRON_API_KEY=... NEMOTRON_FAST_MODEL=... NEMOTRON_REASONING_MODEL=... \\
        python scripts/nemotron_check.py            # from apps/api

Exit 0: every configured role resolved and answered. Exit 1: a configured ID is
missing from the catalog or the test call failed. Exit 2: nothing is configured.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any, Optional

_API_ROOT = Path(__file__).resolve().parents[1]
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

from app.agents.eligibility_agent.llm_split import strip_think  # noqa: E402
from core.config import settings  # noqa: E402


def make_client() -> Any:
    from openai import OpenAI

    return OpenAI(api_key=settings.nemotron_api_key, base_url=settings.nemotron_base_url, timeout=60.0, max_retries=0)


def check(client: Any, roles: dict[str, str]) -> int:
    try:
        catalog = [m.id for m in client.models.list().data]
    except Exception as exc:
        print(f"ERROR: could not list models at {settings.nemotron_base_url} ({type(exc).__name__})")
        return 1
    nemotron = sorted(i for i in catalog if "nemotron" in i.lower())
    print(f"{len(catalog)} models served; {len(nemotron)} mention 'nemotron':")
    for model_id in nemotron:
        print(f"  {model_id}")

    status = 0
    for role, model_id in roles.items():
        if model_id not in catalog:
            close = [i for i in nemotron if i.lower() == model_id.lower()]
            hint = f" (same ID with different casing exists: {close[0]})" if close else ""
            print(f"FAIL {role}: '{model_id}' is not in the catalog{hint}")
            status = 1
            continue
        started = time.monotonic()
        try:
            resp = client.chat.completions.create(
                model=model_id,
                messages=[{"role": "user", "content": "Reply with the single word OK."}],
                max_tokens=32,
            )
            text = resp.choices[0].message.content or ""
        except Exception as exc:
            print(f"FAIL {role}: '{model_id}' test call failed ({type(exc).__name__})")
            status = 1
            continue
        if not strip_think(text).strip():
            print(f"FAIL {role}: '{model_id}' returned no visible text (reasoning only, or empty); raise max_tokens or set NEMOTRON_EXTRA_BODY")
            status = 1
            continue
        note = " (output contains <think>: set NEMOTRON_EXTRA_BODY or rely on stripping)" if "<think>" in text else ""
        print(f"OK   {role}: '{model_id}' answered in {time.monotonic() - started:.1f}s: {strip_think(text)[:40]!r}{note}")
    return status


def main(client: Optional[Any] = None) -> int:
    roles = {
        r: m
        for r, m in (("fast", settings.nemotron_fast_model), ("reasoning", settings.nemotron_reasoning_model))
        if m
    }
    if not settings.nemotron_api_key or not roles:
        print("Nothing to check: set NEMOTRON_API_KEY and NEMOTRON_FAST_MODEL and/or NEMOTRON_REASONING_MODEL.")
        return 2
    return check(client or make_client(), roles)


if __name__ == "__main__":
    sys.exit(main())
