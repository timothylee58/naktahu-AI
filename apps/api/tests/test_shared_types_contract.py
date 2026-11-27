"""packages/shared-types must describe the API the backend really serves (CLAUDE.md Trap #6)."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.agents.router_node import _VALID_DOMAINS
from routers._request_fields import Language as RequestLanguage

_INDEX = Path(__file__).resolve().parents[3] / "packages" / "shared-types" / "index.ts"

pytestmark = pytest.mark.skipif(not _INDEX.exists(), reason="shared-types package not in this checkout")


def _union(name: str) -> set[str]:
    body = re.search(rf"export type {name} =([^;]+);", _INDEX.read_text(encoding="utf-8"))
    assert body, f"{name} not found in shared-types"
    return set(re.findall(r'"([^"]+)"', body.group(1)))


def test_domain_union_matches_router_node() -> None:
    assert _union("Domain") == set(_VALID_DOMAINS)


def test_request_language_matches_request_fields() -> None:
    assert _union("Language") | {"ms"} == set(RequestLanguage.__args__)


def test_sse_event_names_match_what_the_api_emits() -> None:
    from app.routers import query as deployed_query

    emitted = set(re.findall(r'_sse\("(\w+)"', Path(deployed_query.__file__).read_text(encoding="utf-8")))
    declared = set(re.findall(r'event: "(\w+)"', _INDEX.read_text(encoding="utf-8")))
    assert declared == emitted
