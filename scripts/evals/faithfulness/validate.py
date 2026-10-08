"""Validate a human-labelled calibration file before anyone trusts a verdict from it."""
from __future__ import annotations

from collections import Counter
from typing import Any, Sequence

from scripts.evals.faithfulness.metrics import LANGUAGES, MIN_PER_LANGUAGE

MAX_CONTEXT_CHARS = 24_000
BALANCE = (0.30, 0.70)   # share of supported (label 1) claims per language


def validate_cases(rows: Sequence[dict[str, Any]]) -> tuple[list[str], dict[str, str]]:
    """Return (problems, progress). Progress is per-language 'have/need' for REAL rows."""
    problems: list[str] = []
    seen_ids: set[str] = set()
    seen_pairs: set[tuple[str, str]] = set()
    real_by_lang: Counter[str] = Counter()
    pos_by_lang: Counter[str] = Counter()

    for n, r in enumerate(rows, 1):
        rid = str(r.get("id") or f"row{n}")
        if not r.get("id"):
            problems.append(f"{rid}: missing id")
        elif rid in seen_ids:
            problems.append(f"{rid}: duplicate id")
        seen_ids.add(rid)
        if r.get("language") not in LANGUAGES:
            problems.append(f"{rid}: language must be one of {LANGUAGES}, got {r.get('language')!r}")
        for field in ("context", "claim"):
            if not isinstance(r.get(field), str) or not r[field].strip():
                problems.append(f"{rid}: {field} must be non-empty text")
        if isinstance(r.get("context"), str) and len(r["context"]) > MAX_CONTEXT_CHARS:
            problems.append(f"{rid}: context longer than {MAX_CONTEXT_CHARS} chars")
        if r.get("label") not in (0, 1):
            problems.append(f"{rid}: label must be 0 or 1")
        pair = (str(r.get("context", "")).strip(), str(r.get("claim", "")).strip())
        if pair in seen_pairs:
            problems.append(f"{rid}: same context+claim appears twice")
        seen_pairs.add(pair)
        if not r.get("synthetic"):
            if not str(r.get("labeller") or "").strip():
                problems.append(f"{rid}: real rows need a 'labeller' (who judged it)")
            if r.get("language") in LANGUAGES:
                real_by_lang[r["language"]] += 1
                pos_by_lang[r["language"]] += int(r.get("label") == 1)

    for lang in LANGUAGES:
        n = real_by_lang[lang]
        if n >= 10:
            share = pos_by_lang[lang] / n
            if not BALANCE[0] <= share <= BALANCE[1]:
                problems.append(f"{lang}: {share:.0%} of real rows are 'supported'; keep it between {BALANCE[0]:.0%} and {BALANCE[1]:.0%}")
    progress = {lang: f"{real_by_lang[lang]}/{MIN_PER_LANGUAGE}" for lang in LANGUAGES}
    return problems, progress
