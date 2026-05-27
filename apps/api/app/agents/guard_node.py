"""guard_node — topic scope check after routing.

Rejects queries that are clearly outside the Malaysian public-service domain
before RAG retrieval is attempted. Returns a refusal message written via
get_stream_writer() so the SSE endpoint receives it like any other token stream.
"""
from __future__ import annotations

import structlog
from langgraph.config import get_stream_writer

from app.models.state import AgentState

log = structlog.get_logger(__name__)

_VALID_DOMAINS = {
    "government", "education", "legal", "finance",
    "healthcare", "epf", "tax", "business", "immigration", "culture",
}

# Intents that signal out-of-scope requests regardless of domain label
_BLOCKED_INTENT_KEYWORDS = [
    "hack", "crack", "exploit", "malware", "phishing", "keylogger",
    "ddos", "ransomware", "bypass security", "steal credentials",
    "how to cheat", "how to forge", "counterfeit", "scam people",
    "generate fake", "create fake id", "bomb", "weapon", "drug synthesis",
    "make drugs", "synthesize drugs",
]


def _is_blocked_intent(intent: str) -> bool:
    lower = intent.lower()
    return any(kw in lower for kw in _BLOCKED_INTENT_KEYWORDS)


def _refusal_message(lang: str) -> str:
    if lang == "bm":
        return (
            "Maaf, NakTahu AI hanya boleh menjawab soalan berkaitan perkhidmatan awam, "
            "undang-undang, pendidikan, kewangan, kesihatan, dan hal ehwal rakyat Malaysia. "
            "Soalan anda berada di luar skop sistem ini."
        )
    return (
        "Sorry, NakTahu AI is designed to answer questions about Malaysian public services, "
        "law, education, finance, healthcare, and civic affairs. "
        "Your query is outside the scope of this system."
    )


async def guard_node(state: AgentState) -> dict:
    """Block off-topic or harmful queries; let valid ones pass through unchanged."""
    domain: str = state.get("domain", "government")
    intent: str = state.get("intent", "")
    lang: str = state.get("language", "en")

    blocked = domain not in _VALID_DOMAINS or _is_blocked_intent(intent)

    if blocked:
        log.warning("guard_node_blocked", domain=domain, intent=intent)
        write = get_stream_writer()
        msg = _refusal_message(lang)
        # Emit refusal as a single token chunk so the SSE layer handles it uniformly
        write(msg)
        return {"streaming_token_buffer": msg, "needs_clarification": False, "error": "blocked"}

    return {}
