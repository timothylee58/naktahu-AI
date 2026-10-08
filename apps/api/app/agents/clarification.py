"""The bare "I can't answer this" message, in every language the pipeline answers in.

Single source for graph._clarification_node and the streaming path in
KnowledgeQAAdapter.stream — they used to carry separate copies, both with
only Bahasa Malaysia and English, so a Chinese query got an English refusal.
"""
from __future__ import annotations

_MESSAGES = {
    "bm": (
        "Maaf, saya tidak pasti dengan jawapan untuk soalan anda. "
        "Boleh anda berikan lebih maklumat atau nyatakan soalan dengan lebih jelas?"
    ),
    "zh": (
        "抱歉，我无法确定能否准确回答这个问题。"
        "请提供更多背景信息，或换一种方式描述您的问题。"
    ),
    "en": (
        "I'm not confident enough to answer this question accurately. "
        "Could you please provide more context or rephrase your question?"
    ),
}


def clarification_message(language: str | None) -> str:
    """Message for `language`; anything unrecognised gets English."""
    return _MESSAGES.get(language or "en", _MESSAGES["en"])
