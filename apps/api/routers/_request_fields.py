"""Shared bounded-field types for request metadata (language/domain) that
several routers accept alongside a query. Centralised so the valid set
can't drift between routers the way document_chunks.valid_domain and the
router/guard `_VALID_DOMAINS` sets have drifted before (CLAUDE.md Trap #6).

`domain` here intentionally allows "general" in addition to the 10
canonical RAG domains — feedback/history/share entries aren't always tied
to a specific retrieval domain, and "general" is the existing app-wide
sentinel default for that case (see ShareRequest.domain).
"""
from __future__ import annotations

from typing import Literal

# "ms" is accepted as an input alias (some existing callers/tests send it),
# but router_node.py's classification check and guard_node.py's refusal
# message only special-case "bm" — an unnormalised "ms" would silently take
# the "en" fallback path in router_node and the wrong-language refusal copy
# in guard_node. Callers should run normalise_language() as a field
# validator so "bm" is the only value that ever reaches the pipeline.
Language = Literal["bm", "en", "ms", "zh"]
Domain = Literal[
    "government", "education", "legal", "finance", "healthcare",
    "epf", "tax", "business", "immigration", "culture", "general",
]


def normalise_language(v: str) -> str:
    """Fold the "ms" input alias to "bm" after Literal validation.

    Use as `@field_validator("language") @classmethod def _normalise(cls,
    v): return normalise_language(v)` in any model with a `Language` field.
    """
    return "bm" if v == "ms" else v
