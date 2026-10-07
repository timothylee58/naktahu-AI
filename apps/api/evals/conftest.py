"""conftest for apps/api/evals — reuses the tests/ fixtures.

pytest only auto-discovers conftest.py files that are ancestors of the test
file being collected, so evals/ (a sibling of tests/) needs its own
conftest.py. We import the fixtures we need from tests.conftest so the
same Redis/Supabase mocking used by the rest of the suite applies here too.
"""
from __future__ import annotations

from tests.conftest import reset_shared_state

# Explicit re-export: pytest picks the fixture up from this module's
# namespace, and __all__ tells linters the import is intentional rather than
# dead (a bare `# noqa: F401` doesn't satisfy pyflakes, which the CI lint
# step runs).
__all__ = ["reset_shared_state"]

# NOTE: this previously imported `patch_redis_and_supabase_startup` and
# `reset_rate_limiters`, which no longer exist in tests/conftest.py — they
# were consolidated into the autouse `reset_shared_state`. The stale import
# raised ImportError at collection, so `pytest evals/` could not even be
# collected, let alone pass. That is the real reason these three datasets
# were never running: not merely "unwired from CI" but broken outright.
# The eval tests patch their own LLM clients via unittest.mock, so the
# autouse state reset is the only fixture they actually need.
