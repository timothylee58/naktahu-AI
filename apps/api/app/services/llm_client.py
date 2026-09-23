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
# endpoint per docs.ilmu.ai; it was previously api.ilmu.gov.my, a domain that
# doesn't serve ILMU — every call failed with a bare "Connection error."
# (2026-09-23 incident) until ILMU_BASE_URL was set explicitly on Railway.
ilmu_client = AsyncOpenAI(
    api_key=os.environ.get("ILMU_API_KEY", "placeholder"),
    base_url=os.environ.get("ILMU_BASE_URL", "https://api.ilmu.ai/v1"),
)

# Anthropic client — fallback for synthesiser when ILMU fails or confidence < 0.6
anthropic_client = anthropic.AsyncAnthropic(
    api_key=os.environ.get("ANTHROPIC_API_KEY", "placeholder"),
)

# OpenAI client — embeds the `embedding` column of document_chunks (see the
# dual-embedding invariant below). None when OPENAI_API_KEY is unset, in which
# case the OpenAI retrieval path raises and rag_node degrades to no chunks.
_openai_key = os.environ.get("OPENAI_API_KEY", "")
openai_client: AsyncOpenAI | None = AsyncOpenAI(api_key=_openai_key) if _openai_key else None

ILMU_CHAT_MODEL: str = os.environ.get("ILMU_CHAT_MODEL", "ilmu-chat")

# ── Dual-embedding invariant (migration 051) ────────────────────────────────
#
# document_chunks carries TWO embedding columns, one per model:
#
#   embedding       vector(1536)  OPENAI_EMBEDDING_MODEL  -> hybrid_search()
#   embedding_ilmu  vector(4096)  ILMU_EMBEDDING_MODEL    -> hybrid_search_ilmu()
#
# The rule that keeps this safe: a column only ever holds vectors from its own
# model, and each search function is only ever called with a query embedded by
# that same model. Vectors from different models are never compared.
#
# Why that rule matters: two DIFFERENT models of the SAME dimension don't raise
# when compared — pgvector returns a cosine number that means nothing, the
# BM25 half of hybrid_search keeps the results looking plausible, and
# analyst_node cites them with confidence partly derived from noise. The
# 4096/1536 split here happens to make a cross-wire fail loudly (dimension
# mismatch error), but don't rely on that: never feed one column's search with
# the other model's vector, and never write one model's output into the other
# model's column.
#
# History: the live corpus was built with OpenAI text-embedding-3-small
# (verified: all rows 1536-dim). An earlier change (PR #207) assumed it was
# ILMU-embedded and removed OpenAI from the query path, which is what broke
# retrieval once queries started going to the real ILMU — ILMU's embedding
# model is 4096-dim and can't query a 1536-dim corpus at all.
#
# rag_node queries ILMU first (user decision) and falls back to OpenAI when
# the ILMU embed fails, hybrid_search_ilmu fails (e.g. migration 051 not yet
# applied), or it returns nothing (e.g. rows not yet backfilled). All other
# callers (tools, grant_rag_node, ingestion of `embedding`) use OpenAI.
OPENAI_EMBEDDING_MODEL: str = os.environ.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
# ILMU's embedding model ID. Must be ILMU's own model name — an OpenAI name
# here (e.g. "text-embedding-3-small") makes ILMU return 404 model_not_found,
# which rag_node survives by falling back to OpenAI, but ILMU never serves.
ILMU_EMBEDDING_MODEL: str = os.environ.get("ILMU_EMBEDDING_MODEL", "ilmu-embedding")
# Output dimension of ILMU_EMBEDDING_MODEL; must match document_chunks.
# embedding_ilmu's vector(N). Checked before any write so a wrong model or a
# changed dimension fails with a clear message instead of a DB type error.
ILMU_EMBEDDING_DIMS: int = 4096

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
