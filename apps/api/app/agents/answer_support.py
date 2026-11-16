"""Answer-side support check: stop reporting high confidence on an answer that says it has no answer.

analyst_node scores the RETRIEVED CHUNKS (relevance, authority, freshness) before the answer
exists, so its confidence cannot know whether the synthesiser then found the answer in them. A
live eval showed the result: answers such as "I could not find the spouse relief amount in the
provided documents" went out at confidence 0.81, and the UI showed official-source chips under them.

This module looks at the finished answer. When its opening sentence says the context does not
contain the answer, the confidence is capped below the clarification bar and the answer is
flagged for follow-up. It can only LOWER confidence: it never raises it, never touches
analyst_node, and never changes the 0.6 bar. The opposite miscalibration (a correct answer at low
confidence) is a retrieval-quality problem and is fixed in the corpus, not by loosening a gate.
"""
from __future__ import annotations

import re
from typing import Any, Mapping

# Below analyst_node's 0.6 clarification bar, so a declined answer is always flagged.
DECLINE_CONFIDENCE_CEILING = 0.35

# Only the opening sentence is judged, and a sentence that contains a figure is giving an answer, not
# declining: "The documents do not mention penalties, but the deadline is 30 April" is not a decline,
# "I could not find the spouse relief amount in the provided documents" is.
_OPENING_MAX_CHARS = 300
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+|[。！？\n]")
_MARKDOWN = re.compile(r"[*_`#>]+")

_DECLINE_PHRASES = (
    # English
    "could not find", "couldn't find", "cannot find", "can't find", "unable to find",
    "did not find", "do not contain", "does not contain", "do not specify", "does not specify",
    "do not provide", "does not provide", "do not mention", "does not mention", "not mentioned",
    "not specified in", "not provided in", "no relevant information", "no information",
    "i cannot provide", "i can't provide",
    "i cannot answer", "i don't have information", "i do not have information",
    "no specific", "no explicit", "no mention of", "no details",
    # Bahasa Malaysia
    "tidak dapat mencari", "tidak dapat menemui", "tidak menemui", "tidak mengandungi",
    "tidak menyatakan", "tidak dinyatakan", "tidak dapat memberikan", "tidak dapat menjawab",
    "tiada maklumat", "tidak ada maklumat", "tidak terdapat maklumat",
    # Chinese
    "没有找到", "未找到", "找不到", "没有相关", "未提及", "没有提到", "不包含", "无法提供", "无法回答",
)


# A decline is a statement about the PROVIDED material ("the context does not contain...") or a first-person
# "I could not find...". Without that, "There is no specific deadline for keeping receipts" is a real answer.
_GROUNDING = (
    "context", "document", "provided", "given", "source", "excerpt", "passage", "material",
    "konteks", "dokumen", "sumber", "diberikan", "上下文", "文档", "资料", "来源", "提供",
)
_FIRST_PERSON = ("i ", "i'm ", "i\u2019m ", "saya ", "我")


def answer_declines(text: str) -> bool:
    """True when the answer's opening sentence says the provided context has no answer."""
    cleaned = _MARKDOWN.sub("", text or "").replace("\u2019", "'").strip()
    if not cleaned:
        return False
    opening = _SENTENCE_END.split(cleaned, maxsplit=1)[0][:_OPENING_MAX_CHARS].lower()
    if any(ch.isdigit() for ch in opening):
        return False
    if not any(phrase in opening for phrase in _DECLINE_PHRASES):
        return False
    return opening.startswith(_FIRST_PERSON) or any(word in opening for word in _GROUNDING)


def apply_support_check(state: Mapping[str, Any], answer_text: str) -> dict[str, Any]:
    """State updates for the synthesiser to return. Empty-handed unless the answer declines.

    A decline with no figures in it has nothing a source chip could support, so its citations are
    dropped (chips under "I could not find it" read as endorsements). A decline that still carries
    figures, such as an announced change offered in place of the missing current rule, keeps them.
    """
    if not answer_declines(answer_text):
        return {"answer_declined": False}
    update: dict[str, Any] = {
        "answer_declined": True,
        "confidence_score": min(float(state.get("confidence_score") or 0.0), DECLINE_CONFIDENCE_CEILING),
        "needs_clarification": True,
    }
    if not any(ch.isdigit() for ch in answer_text):
        update["citations"] = []
    return update
