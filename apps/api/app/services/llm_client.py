"""LLM provider abstraction.

ILMU (OpenAI-compatible) is the primary provider for both chat and embeddings.
Anthropic claude-sonnet-4-20250514 is the fallback for the synthesiser only.
"""
from __future__ import annotations

import json
import os

import anthropic
from openai import AsyncOpenAI

# ILMU client — OpenAI SDK pointed at ILMU base URL
ilmu_client = AsyncOpenAI(
    api_key=os.environ.get("ILMU_API_KEY", "placeholder"),
    base_url=os.environ.get("ILMU_BASE_URL", "https://api.ilmu.gov.my/v1"),
)

# Anthropic client — fallback for synthesiser when ILMU fails or confidence < 0.6
anthropic_client = anthropic.AsyncAnthropic(
    api_key=os.environ.get("ANTHROPIC_API_KEY", "placeholder"),
)

# OpenAI client — fallback for embeddings when ILMU embeddings unavailable
_openai_key = os.environ.get("OPENAI_API_KEY", "")
openai_client: AsyncOpenAI | None = AsyncOpenAI(api_key=_openai_key) if _openai_key else None

ILMU_CHAT_MODEL: str = os.environ.get("ILMU_CHAT_MODEL", "ilmu-chat")
ILMU_EMBEDDING_MODEL: str = os.environ.get("ILMU_EMBEDDING_MODEL", "ilmu-embedding")
OPENAI_EMBEDDING_MODEL: str = os.environ.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
FALLBACK_MODEL: str = "claude-sonnet-4-20250514"


def extract_json_object(raw: str) -> dict:
    """Extract the first well-formed JSON object from a raw LLM completion.

    Robust to markdown code fences and trailing commentary after the JSON
    (e.g. '{...} Let me know if you need anything else!') — a naive greedy
    regex like r'\\{.*\\}' matches from the first '{' to the LAST '}' in the
    whole completion, so it corrupts parsing the moment the model appends
    any text containing a brace, silently discarding an otherwise-correct
    classification. Uses JSONDecoder.raw_decode to parse only the first
    balanced object starting at the first '{', ignoring everything after it
    — no dependence on where (or whether) a matching closing brace appears
    later in unrelated trailing text.
    """
    start = raw.find("{")
    if start == -1:
        return {}
    try:
        obj, _ = json.JSONDecoder().raw_decode(raw[start:])
    except (ValueError, json.JSONDecodeError):
        return {}
    return obj if isinstance(obj, dict) else {}
