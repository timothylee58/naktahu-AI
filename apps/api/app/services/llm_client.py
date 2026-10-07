"""LLM provider abstraction.

ILMU (OpenAI-compatible) is the primary provider for both chat and embeddings.
Anthropic claude-sonnet-5 is the fallback for the synthesiser only.
"""
from __future__ import annotations

import json
import os

import anthropic
from openai import AsyncOpenAI

# ILMU client — OpenAI SDK pointed at ILMU base URL. Default is ILMU's real
# endpoint per docs.ilmu.ai; it was previously api.ilmu.gov.my, which doesn't
# serve ILMU — every call failed with a bare "Connection error." (2026-09-23
# incident) until ILMU_BASE_URL was set explicitly on Railway.
ilmu_client = AsyncOpenAI(
    api_key=os.environ.get("ILMU_API_KEY", "placeholder"),
    base_url=os.environ.get("ILMU_BASE_URL", "https://api.ilmu.ai/v1"),
)

# Anthropic client — fallback for synthesiser when ILMU fails or confidence < 0.6
anthropic_client = anthropic.AsyncAnthropic(
    api_key=os.environ.get("ANTHROPIC_API_KEY", "placeholder"),
)

# OpenAI client — direct fallback for embeddings (see the invariant below).
# None when OPENAI_API_KEY is unset; the fallback is then simply unavailable.
_openai_key = os.environ.get("OPENAI_API_KEY", "")
openai_client: AsyncOpenAI | None = AsyncOpenAI(api_key=_openai_key) if _openai_key else None

ILMU_CHAT_MODEL: str = os.environ.get("ILMU_CHAT_MODEL", "ilmu-chat")

# ── Embeddings: ONE model, two routes to it ─────────────────────────────────
#
# The embedding model is a property of the CORPUS, never a per-request choice.
# document_chunks.embedding is vector(1536) and was built with OpenAI
# text-embedding-3-small (verified against production 2026-09-23: every row
# is 1536-dim). Every query and every write must use that same model.
#
# ILMU is a gateway that serves OpenAI's v3 embedding models itself (docs.ilmu.ai
# Embeddings -> per-model limits: "OpenAI v3, native 1536"). So the same model
# is reachable two ways, and rag_node._embed tries them in order:
#   1. ILMU gateway   ILMU_EMBEDDING_MODEL   = "openai/text-embedding-3-small"
#   2. OpenAI direct  OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"
# Falling back between them is safe ONLY because it's the same model — same
# weights, same vector space.
#
# Why that condition is non-negotiable: two DIFFERENT models of the same
# dimension don't raise when compared — pgvector returns a cosine number that
# means nothing, hybrid_search's BM25 half keeps results looking plausible, and
# analyst_node cites them with confidence partly derived from noise. On the
# write side, scripts/ingest_feed.py would permanently mix vector spaces in one
# column. So _embed refuses the ILMU route unless ILMU_EMBEDDING_MODEL names the
# same model as OPENAI_EMBEDDING_MODEL (see embedding_routes_share_a_model).
#
# Switching to a genuinely different model (e.g. ILMU-hosted bge-m3 or Gemini)
# is a corpus migration — re-embed every row — never a runtime fallback.
OPENAI_EMBEDDING_MODEL: str = os.environ.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
ILMU_EMBEDDING_MODEL: str = os.environ.get("ILMU_EMBEDDING_MODEL", "openai/text-embedding-3-small")
# Dimension of document_chunks.embedding. Both routes are checked against it,
# so a misconfigured model fails loudly instead of writing/querying a
# wrong-shaped vector.
EMBEDDING_DIMS: int = 1536


def embedding_routes_share_a_model(ilmu_model: str, openai_model: str) -> bool:
    """True when the ILMU gateway model ID names the same model as the direct
    OpenAI one (ILMU prefixes the provider: "openai/text-embedding-3-small")."""
    return ilmu_model.rsplit("/", 1)[-1] == openai_model and ilmu_model.startswith("openai/")

# claude-sonnet-4-20250514 was retired by Anthropic — confirmed 2026-09-23 via
# a live production 404 from the Anthropic API itself ("not_found_error,
# model: claude-sonnet-4-20250514"), not a guess. That 404 was firing on
# every synthesiser-fallback attempt during a real ILMU outage (Railway logs,
# same incident: router_node_error/rag_retrieval_failed "Connection error."
# on 100% of requests since the last deploy) — meaning the fallback this
# constant exists for was itself unusable for the entire time ILMU was down.
# claude-sonnet-5 is the current model in the same tier (Sonnet), not an
# upgrade to Opus or downgrade to Haiku — same synthesis-quality intent this
# constant always had, just pointed at a snapshot Anthropic still serves.
FALLBACK_MODEL: str = "claude-sonnet-5"


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
