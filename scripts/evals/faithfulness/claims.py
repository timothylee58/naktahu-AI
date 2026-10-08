"""Split an answer into claims, for claim-level faithfulness judging.

RAGAS decomposes an answer into atomic claims with an LLM. This is a coarser,
deterministic, language-agnostic stand-in: one claim per sentence. A sentence
that states two facts, only one of them wrong, is judged as a single claim, so
this can understate unfaithfulness. It is good enough to pilot a judge; it is
not a substitute for atomic decomposition if the pilot graduates.
"""
from __future__ import annotations

import re

# Abbreviations whose trailing '.' must not end a sentence (Malay and English).
_ABBREVIATIONS = ("Sdn.", "Bhd.", "No.", "Dr.", "Hj.", "Hjh.", "Tn.", "Pn.", "Bil.", "bil.", "etc.", "vs.", "St.")
_PLACEHOLDER = "\u0000"

_LEADING_MARKER = re.compile(r"^\s*(?:[-*•]+|\d{1,2}[.)])\s+")
_CITATION = re.compile(r"\[\d{1,3}\]")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+|(?<=[。！？])")
_CJK = re.compile(r"[一-鿿]")


def _substantive(sentence: str) -> bool:
    """Drop fragments too short to carry a checkable fact."""
    letters = sum(ch.isalnum() for ch in sentence)
    return letters >= (5 if _CJK.search(sentence) else 8)


def split_claims(answer: str, *, max_claims: int = 20) -> list[str]:
    text = answer or ""
    for abbr in _ABBREVIATIONS:
        text = text.replace(abbr, abbr[:-1] + _PLACEHOLDER)
    claims: list[str] = []
    for line in text.splitlines():
        line = _CITATION.sub("", _LEADING_MARKER.sub("", line))
        for sentence in _SENTENCE_END.split(line):
            sentence = " ".join(sentence.replace(_PLACEHOLDER, ".").split())
            if sentence and _substantive(sentence):
                claims.append(sentence)
    return claims[:max_claims]
