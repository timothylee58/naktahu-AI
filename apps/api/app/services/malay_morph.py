"""Malay affix expansion for the keyword half of hybrid_search.

hybrid_search's keyword layer uses Postgres's ``simple`` text config, which
does no stemming (and Postgres ships no Malay stemmer). So the affixed forms
of one Malay root are unrelated tokens: a query for "cara memohon" never
keyword-matches a chunk that says "permohonan", even though both are the root
"mohon". That silently drops the exact-term boost for most BM queries.

Instead of stemming the corpus (which would need a re-index and a custom
Postgres dictionary), we expand the QUERY: each Latin-script token is turned
into an OR-group of its likely roots plus the common derived forms of those
roots, and the groups are AND-ed — the same AND semantics plainto_tsquery had,
just morphology-aware. The result is passed to hybrid_search as
``keyword_query`` (migration 051) and parsed with to_tsquery('simple', ...).

Deliberately heuristic: it over-generates (most variants simply never occur in
the corpus and cost nothing) rather than trying to be a correct stemmer.
English tokens pass through with harmless junk variants. Non-Latin tokens
(e.g. CJK) are left out — ``build_keyword_tsquery`` returns None when there is
nothing to expand and the RPC then falls back to plainto_tsquery.
"""
from __future__ import annotations

import re

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_VOWELS = set("aeiou")

# Shortest root we will generate variants from. 3-letter "roots" like "apa"
# (from "berapa") would OR-in very common words and hurt precision.
_MIN_ROOT = 4
# Bounds keep the tsquery small however long the user's query is.
_MAX_GROUPS = 8
_MAX_VARIANTS = 64

_PARTICLES = ("nya", "lah", "kah", "pun")
_SUFFIXES = ("kan", "an", "i")


def _men(root: str, base: str) -> str:
    """Attach the nasal prefix meN-/peN- (``base`` is "me" or "pe")."""
    first = root[0]
    if root.startswith(("ng", "ny")) or first in "lmnrwy":
        return base + root
    if first in _VOWELS or first in "gh":
        return base + "ng" + root
    if first == "k":
        return base + "ng" + root[1:]
    if first == "p":
        return base + "m" + root[1:]
    if first in "bfv":
        return base + "m" + root
    if first == "t":
        return base + "n" + root[1:]
    if first in "dcjz":
        return base + "n" + root
    if first == "s":
        return base + "ny" + root[1:]
    return base + root


def _strip_prefix(word: str) -> list[str]:
    """Candidate stems after removing one prefix, restoring nasal-dropped letters."""
    out: list[str] = []
    for nasal, base in (("meny", "me"), ("peny", "pe")):
        if word.startswith(nasal):
            out.append("s" + word[len(nasal):])
    for nasal in ("meng", "peng"):
        if word.startswith(nasal):
            rest = word[4:]
            out.append(rest)
            if rest and rest[0] in _VOWELS:
                out.append("k" + rest)  # mengira -> kira
    for nasal in ("mem", "pem"):
        if word.startswith(nasal):
            rest = word[3:]
            out.append(rest)  # membayar -> bayar
            if rest and rest[0] in _VOWELS:
                out.append("p" + rest)  # memohon -> pohon (and mohon below)
    for nasal in ("men", "pen"):
        if word.startswith(nasal) and not word.startswith(("meng", "peng", "meny", "peny")):
            rest = word[3:]
            out.append(rest)  # mendaftar -> daftar
            if rest and rest[0] in _VOWELS:
                out.append("t" + rest)  # menulis -> tulis
    for prefix in ("me", "pe", "ber", "be", "ter", "di", "ke", "se", "per"):
        if word.startswith(prefix):
            out.append(word[len(prefix):])  # memohon -> mohon, permohonan -> mohonan
    return out


def _strip_suffix(word: str) -> list[str]:
    out: list[str] = []
    for s in _SUFFIXES:
        if word.endswith(s):
            out.append(word[: -len(s)])
    return out


def candidate_roots(word: str) -> set[str]:
    """Plausible roots of ``word`` (including the word itself)."""
    w = word
    for p in _PARTICLES:
        if w.endswith(p) and len(w) - len(p) >= _MIN_ROOT:
            w = w[: -len(p)]
            break
    roots = {w}
    for stem in [w, *_strip_suffix(w)]:
        roots.add(stem)
        for pre in _strip_prefix(stem):
            roots.add(pre)
            roots.update(_strip_suffix(pre))
    return {r for r in roots if len(r) >= _MIN_ROOT}


def derived_forms(root: str) -> list[str]:
    """Common affixed forms of ``root``."""
    me, pe = _men(root, "me"), _men(root, "pe")
    return [
        root, root + "kan", root + "an", root + "i",
        me, me + "kan", me + "i",
        pe, pe + "an", "per" + root + "an", "ke" + root + "an",
        "di" + root, "di" + root + "kan", "di" + root + "i",
        "ber" + root, "ter" + root,
    ]


def expand_token(word: str) -> list[str]:
    """OR-group for one token: the token first, then roots and derived forms."""
    seen: dict[str, None] = {word: None}
    # Derive from the stripped roots shortest first (the true root is usually
    # the shortest stem), and from the surface word last: "cukai" is itself a
    # root, but for an affixed word its derivations ("mememohon") are junk
    # that the variant cap should cut first.
    roots = sorted(candidate_roots(word) - {word}, key=lambda r: (len(r), r)) + [word]
    for root in roots:
        for form in derived_forms(root):
            seen.setdefault(form, None)
    return list(seen)[:_MAX_VARIANTS]


# Cross-language terms that name the same thing. Dense retrieval bridges these
# on its own, but the keyword half of hybrid_search does not: "Bajet 2027" never
# keyword-matches a document titled "Belanjawan 2027", and "EPF" never matches
# "KWSP". Single-token pairs only, kept deliberately short and unambiguous:
# `grant`/`geran` is left out because `geran` also means a land title in
# Malaysian usage, and expanding it would pull in unrelated property text.
_SYNONYM_GROUPS: tuple[tuple[str, ...], ...] = (
    ("budget", "bajet", "belanjawan"),
    ("tax", "cukai"),
    ("rate", "kadar"),
    ("income", "pendapatan"),
    ("relief", "pelepasan"),
    ("epf", "kwsp"),
    ("socso", "perkeso"),
    ("withdrawal", "pengeluaran"),
    ("contribution", "caruman"),
    ("retirement", "persaraan"),
    ("subsidy", "subsidi"),
    ("loan", "pinjaman"),
    ("passport", "pasport"),
    ("licence", "license", "lesen"),
    ("allowance", "elaun"),
    ("employer", "majikan"),
    ("employee", "pekerja"),
    ("salary", "wage", "gaji"),
    ("housing", "perumahan"),
    ("school", "sekolah"),
    ("health", "kesihatan"),
    ("scholarship", "biasiswa"),
    ("inflation", "inflasi"),
    ("deficit", "defisit"),
    ("allocation", "peruntukan"),
    ("expenditure", "perbelanjaan"),
)
_SYNONYMS: dict[str, tuple[str, ...]] = {
    term: tuple(other for other in group if other != term)
    for group in _SYNONYM_GROUPS
    for term in group
}
# Each synonym contributes itself plus a few of its own affixed forms.
_SYNONYM_VARIANTS = 12


def _with_synonyms(token: str, variants: list[str]) -> list[str]:
    extra: list[str] = []
    for synonym in _SYNONYMS.get(token, ()):
        extra.append(synonym)
        if synonym.isalpha() and len(synonym) >= _MIN_ROOT:
            extra.extend(expand_token(synonym)[:_SYNONYM_VARIANTS])
    return list(dict.fromkeys([*variants, *extra]))


def build_keyword_tsquery(query: str) -> str | None:
    """Build a to_tsquery('simple', ...) string, or None if nothing to expand.

    Only ``[a-z0-9]`` tokens survive, so the output can never contain tsquery
    operators from user input (no injection into the tsquery grammar).
    """
    tokens = _TOKEN_RE.findall(query.lower())
    groups: list[str] = []
    seen: set[str] = set()
    for tok in tokens:
        if tok in seen:
            continue
        seen.add(tok)
        variants = expand_token(tok) if tok.isalpha() and len(tok) >= _MIN_ROOT else [tok]
        # Outside the length gate on purpose: "tax" and "epf" are under 4 letters.
        variants = _with_synonyms(tok, variants)
        groups.append("(" + " | ".join(variants) + ")")
        if len(groups) >= _MAX_GROUPS:
            break
    return " & ".join(groups) if groups else None
