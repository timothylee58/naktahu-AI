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


# A model often restates what the context DOES contain first and only then says it lacks the answer
# ("The documents detail withholding rates of 10% to 15%. However, the context does not contain the
# rate for a non-resident individual."). The second sentence counts, but only when it opens like a
# decline AND is about the question: a side remark ("the documents do not mention a rebate") is not.
_SECOND_SENTENCE_LEADS = (
    "however", "but ", "unfortunately", "yet ", "there is no ", "there are no ",
    "namun", "tetapi", "walau bagaimanapun", "tiada ", "但是", "然而", "不过",
)
_QUESTION_OVERLAP_MIN = 2
_WORD = re.compile(r"[a-z]{4,}")
_FILLER = frozenset("what which that this with from about does have your their there where when into than then".split())


def _content_words(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.lower()) if w not in _FILLER}


def _is_decline_sentence(sentence: str) -> bool:
    if any(ch.isdigit() for ch in sentence):
        return False
    if not any(phrase in sentence for phrase in _DECLINE_PHRASES):
        return False
    return sentence.startswith(_FIRST_PERSON) or any(word in sentence for word in _GROUNDING)


def answer_declines(text: str, query: str = "") -> bool:
    """True when the answer says the provided context has no answer.

    The opening sentence is judged on its own. With the question supplied, a second sentence that
    leads like a decline and shares at least two content words with the question counts too.
    """
    cleaned = _MARKDOWN.sub("", text or "").replace("\u2019", "'").strip()
    if not cleaned:
        return False
    sentences = [part for part in _SENTENCE_END.split(cleaned) if part and part.strip()]
    opening = sentences[0][:_OPENING_MAX_CHARS].lower()
    if _is_decline_sentence(opening):
        return True
    if query and len(sentences) > 1:
        second = sentences[1][:_OPENING_MAX_CHARS].lower().lstrip(" ,;:-")
        if second.startswith(_SECOND_SENTENCE_LEADS) and _is_decline_sentence(second):
            return len(_content_words(second) & _content_words(query)) >= _QUESTION_OVERLAP_MIN
    return False


def apply_support_check(state: Mapping[str, Any], answer_text: str) -> dict[str, Any]:
    """State updates for the synthesiser to return. Empty-handed unless the answer declines.

    A decline with no figures in it has nothing a source chip could support, so its citations are
    dropped (chips under "I could not find it" read as endorsements). A decline that still carries
    figures, such as an announced change offered in place of the missing current rule, keeps them.
    """
    if not answer_declines(answer_text, str(state.get("query") or "")):
        return {"answer_declined": False}
    update: dict[str, Any] = {
        "answer_declined": True,
        "confidence_score": min(float(state.get("confidence_score") or 0.0), DECLINE_CONFIDENCE_CEILING),
        "needs_clarification": True,
    }
    if not any(ch.isdigit() for ch in answer_text):
        update["citations"] = []
    return update
