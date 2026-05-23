"""LLM provider abstraction.

ILMU (OpenAI-compatible) is the primary provider for both chat and embeddings.
Anthropic claude-sonnet-4-20250514 is the fallback for the synthesiser only.
"""
from __future__ import annotations

import os

import anthropic
from openai import AsyncOpenAI

# ILMU client — OpenAI SDK pointed at ILMU base URL
ilmu_client = AsyncOpenAI(
    api_key=os.environ.get("ILMU_API_KEY", "placeholder"),
    base_url=os.environ.get("ILMU_BASE_URL", "https://api.ilmu.gov.my/v1"),
)

# Anthropic client — fallback for synthesiser when ILMU fails or confidence < 0.4
anthropic_client = anthropic.AsyncAnthropic(
    api_key=os.environ.get("ANTHROPIC_API_KEY", "placeholder"),
)

ILMU_CHAT_MODEL: str = os.environ.get("ILMU_CHAT_MODEL", "ilmu-chat")
ILMU_EMBEDDING_MODEL: str = os.environ.get("ILMU_EMBEDDING_MODEL", "ilmu-embedding")
FALLBACK_MODEL: str = "claude-sonnet-4-20250514"
