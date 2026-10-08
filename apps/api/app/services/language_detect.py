"""Deterministic English / Bahasa Malaysia / Chinese checks.

router_node asks an LLM which language a query is in, and that LLM is
Malaysia-tuned: it has labelled plain English questions "bm" in production
(an English MyKad question was answered in Bahasa Malaysia). The query's own
words are the authority, so these checks run after the LLM and override it
when they are confident.

Deliberately function-word voting, not a language-ID model: no new dependency,
no model download, and a handful of very common words per language decide
short civic questions reliably. Content words ("MyKad", "EPF", agency names)
are shared across languages and are never counted. Returning None means "not
sure" and the caller keeps whatever it already had.
"""
from __future__ import annotations

import re

_CJK_RE = re.compile(r"[一-鿿㐀-䶿豈-﫿]")
_URL_RE = re.compile(r"https?://\S+")
_WORD_RE = re.compile(r"[a-z]+(?:['’][a-z]+)?")

# Words in BOTH lists would cancel out, so a word only appears where the
# other language does not use it. Left out on purpose: "can", "no", "ok", "so",
# "la" (all common in Manglish) and "me" (a stem in many BM words).
_EN_WORDS = frozenset({
    "the", "is", "are", "was", "were", "be", "been", "am", "a", "an",
    "what", "what's", "how", "why", "when", "where", "which", "who",
    "do", "does", "did", "should", "would", "could", "will", "shall",
    "i", "i'm", "i've", "my", "you", "your", "you're", "we", "our",
    "it", "it's", "its", "this", "that", "these", "those", "there",
    "they", "their", "to", "of", "for", "with", "if", "and", "or", "not",
    "don't", "can't", "isn't", "doesn't", "have", "has", "had", "from",
    "about", "after", "before", "in", "on", "at", "by", "need", "get",
})
_BM_WORDS = frozenset({
    "dan", "yang", "untuk", "saya", "aku", "kami", "kita", "anda", "awak",
    "kamu", "dia", "mereka", "ini", "itu", "ialah", "adalah", "ada", "adakah",
    "apa", "apakah", "bagaimana", "bagaimanakah", "macam", "mana", "bila",
    "bilakah", "kenapa", "mengapa", "siapa", "berapa", "boleh", "tak",
    "tidak", "nak", "hendak", "mahu", "perlu", "kena", "jika", "kalau",
    "atau", "dengan", "di", "ke", "dari", "pada", "sudah", "dah", "belum",
    "akan", "sedang", "kat", "sila", "tolong", "sekarang", "cara", "syarat",
    "hilang", "kehilangan", "mohon", "memohon", "permohonan", "bayar",
})

# Both a minimum number of votes and a 2:1 margin, so one stray English word
# in a Malay sentence (or vice versa) can't flip the answer.
_MIN_VOTES = 2
_MARGIN = 2

# Share of letters that must be Chinese characters for a translation into
# Chinese to count as Chinese. Low on purpose: acronyms and agency names stay
# in Latin script ("JPN", "MyKad") inside an otherwise Chinese answer.
_MIN_CJK_SHARE = 0.25
_MIN_LETTERS_TO_JUDGE = 8


def detect_latin_language(text: str) -> str | None:
    """'en' or 'bm' when the words clearly say so, else None (not sure)."""
    words = _WORD_RE.findall(text.lower())
    en = sum(1 for w in words if w in _EN_WORDS)
    bm = sum(1 for w in words if w in _BM_WORDS)
    lead, trail = (en, bm) if en >= bm else (bm, en)
    if lead < _MIN_VOTES or lead < _MARGIN * trail:
        return None
    return "en" if en > bm else "bm"


def output_matches_language(text: str, target: str) -> bool:
    """False only when `text` is clearly NOT written in `target` (en/bm/zh).

    Used to reject a translation that came back untranslated. Errs toward
    True: text too short or too mixed to judge passes, because rejecting a
    good translation is worse than letting through an unjudgeable one.
    """
    visible = _URL_RE.sub(" ", text)
    cjk = len(_CJK_RE.findall(visible))
    latin = len(re.findall(r"[A-Za-z]", visible))
    if target == "zh":
        total = cjk + latin
        # Too short to judge: "RM10" or "JPN" has no Chinese form to demand.
        return total < _MIN_LETTERS_TO_JUDGE or cjk / total >= _MIN_CJK_SHARE
    if cjk and cjk >= latin:
        return False
    detected = detect_latin_language(visible)
    return detected is None or detected == target
