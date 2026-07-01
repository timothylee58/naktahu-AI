"""conftest for apps/api/evals — reuses the tests/ fixtures.

pytest only auto-discovers conftest.py files that are ancestors of the test
file being collected, so evals/ (a sibling of tests/) needs its own
conftest.py. We import the fixtures we need from tests.conftest so the
same Redis/Supabase mocking used by the rest of the suite applies here too.
"""
from __future__ import annotations

from tests.conftest import (  # noqa: F401  (re-exported as fixtures)
    patch_redis_and_supabase_startup,
    reset_rate_limiters,
)
