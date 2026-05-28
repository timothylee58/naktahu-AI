"""W&B Weave tracing initialisation.

Call `init_weave()` once at startup. It is a no-op when WANDB_API_KEY is
absent so local dev works without credentials.

Each pipeline node is wrapped with @weave.op so every query produces a
structured trace:

  query_pipeline
  ├── router_node
  ├── guard_node
  ├── rag_node
  ├── analyst_node
  └── synthesiser_node (tokens aggregated, not streamed)
"""
from __future__ import annotations

import os

import structlog

log = structlog.get_logger(__name__)

_weave_enabled = False


def init_weave() -> None:
    """Initialise Weave if WANDB_API_KEY is set; silently skip otherwise."""
    global _weave_enabled
    api_key = os.environ.get("WANDB_API_KEY", "")
    project = os.environ.get("WANDB_PROJECT", "naktahu-ai")
    if not api_key:
        log.info("weave_disabled", reason="WANDB_API_KEY not set")
        return
    try:
        import weave
        weave.init(project)
        _weave_enabled = True
        log.info("weave_initialised", project=project)
    except Exception as exc:
        log.warning("weave_init_failed", error=str(exc))


def is_enabled() -> bool:
    return _weave_enabled
