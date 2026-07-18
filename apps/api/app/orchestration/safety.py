"""Unified output safety scanner — shared across all agents.

Extracted from app/agents/synthesiser_node.py so every agent adapter gets
the same post-generation safety check. The synthesiser_node now imports
from here instead of maintaining its own copy.

Two scan layers:
1. INJECTION_PATTERNS (from app/middleware/sanitise.py) — catch prompt
   injection patterns that may have leaked through via RAG chunk content.
2. OUTPUT_ONLY_PATTERNS — patterns specific to model output (identity breaks,
   system-prompt leakage, jailbreak confirmations) that wouldn't appear in
   raw user queries.

The scanner is intentionally cheap (regex-only, no LLM call) and runs once
on the accumulated text after generation completes. It cannot un-stream
tokens already sent via SSE, but it:
- Blocks the response from being persisted into session history
- Surfaces the incident to monitoring (structlog + Sentry)
- Sets output_flagged=True on the AgentResult for downstream handling
"""
from __future__ import annotations

import re
from typing import Optional

import structlog

from app.middleware.sanitise import INJECTION_PATTERNS

log = structlog.get_logger(__name__)

# Patterns specific to *model output* — identity breaks, system-prompt leakage,
# jailbreak confirmations. These wouldn't appear in a normal user query.
OUTPUT_ONLY_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"\bas\s+DAN\b",
        r"i\s+am\s+now\s+unrestricted",
        r"i\s+(?:am|'m)\s+no\s+longer\s+bound\s+by",
        r"ignoring\s+my\s+(?:previous|prior)\s+instructions",
        r"my\s+system\s+prompt\s+(?:is|says|states)",
        r"here\s+(?:is|are)\s+my\s+(?:system\s+)?instructions",
        r"you\s+are\s+NakTahu\s+AI.{0,80}(?:but|however|ignore|override|now\s+act)",
    ]
]

# Combined list: input-side injection + output-side red flags
ALL_OUTPUT_PATTERNS = INJECTION_PATTERNS + OUTPUT_ONLY_PATTERNS


def scan_output(text: str) -> bool:
    """Return True if the text matches a known red-flag pattern.

    This is the shared function all agent adapters call after receiving
    output. Cheap regex-list scan — no extra LLM call.
    """
    if not text:
        return False
    for pattern in ALL_OUTPUT_PATTERNS:
        if pattern.search(text):
            return True
    return False


def scan_and_log(
    text: str,
    *,
    agent_name: str = "",
    session_id: str = "",
    user_id: str = "",
    query: str = "",
) -> bool:
    """Scan output and log a warning if flagged.

    Returns True if the output is flagged (unsafe).
    Callers should set output_flagged=True and skip_history_persist=True.
    """
    flagged = scan_output(text)
    if flagged:
        log.warning(
            "output_safety_flagged",
            agent_name=agent_name,
            session_id=session_id,
            user_id=user_id,
            query=query[:200] if query else "",
            flagged_content=text[:500],
        )
    return flagged


class SafetyReport:
    """Structured safety scan result for observability."""

    def __init__(self, flagged: bool, agent_name: str, text_length: int) -> None:
        self.flagged = flagged
        self.agent_name = agent_name
        self.text_length = text_length
        self.matched_pattern: Optional[str] = None

    @classmethod
    def scan(
        cls,
        text: str,
        *,
        agent_name: str = "",
        session_id: str = "",
        user_id: str = "",
    ) -> "SafetyReport":
        """Run the safety scan and return a structured report."""
        report = cls(flagged=False, agent_name=agent_name, text_length=len(text))
        if not text:
            return report

        for pattern in ALL_OUTPUT_PATTERNS:
            match = pattern.search(text)
            if match:
                report.flagged = True
                report.matched_pattern = pattern.pattern[:80]
                log.warning(
                    "output_safety_flagged",
                    agent_name=agent_name,
                    session_id=session_id,
                    user_id=user_id,
                    pattern=report.matched_pattern,
                    flagged_content=text[:500],
                )
                break

        return report
