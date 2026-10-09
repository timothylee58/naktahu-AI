"""Calibration metrics and the verdict on whether a judge can be trusted to gate CI.

Pure Python (no numpy/sklearn): the eval-gate CI job installs almost nothing.
"""
from __future__ import annotations

from typing import Any, Optional, Sequence

LANGUAGES = ("bm", "en", "zh")
MIN_PER_LANGUAGE = 30      # below this a per-language number is noise
AUROC_MIN = 0.85
ACCURACY_MIN = 0.80        # per language, at threshold 0.5
ECE_MAX = 0.15
BASELINE_MARGIN = 0.05     # must beat the lexical baseline's AUROC by this much


def accuracy(labels: Sequence[int], scores: Sequence[float], threshold: float = 0.5) -> float:
    if not labels:
        return 0.0
    return sum((s >= threshold) == bool(y) for y, s in zip(labels, scores)) / len(labels)


def auroc(labels: Sequence[int], scores: Sequence[float]) -> Optional[float]:
    """Probability a random supported claim outranks a random unsupported one
    (rank-sum with average ranks for ties). None if only one class is present."""
    pos = sum(1 for y in labels if y)
    neg = len(labels) - pos
    if pos == 0 or neg == 0:
        return None
    order = sorted(range(len(scores)), key=lambda i: scores[i])
    ranks = [0.0] * len(scores)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and scores[order[j + 1]] == scores[order[i]]:
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    rank_sum_pos = sum(r for r, y in zip(ranks, labels) if y)
    return (rank_sum_pos - pos * (pos + 1) / 2) / (pos * neg)


def ece(labels: Sequence[int], scores: Sequence[float], bins: int = 10) -> float:
    """Expected calibration error: how far stated confidence is from observed accuracy."""
    if not labels:
        return 0.0
    buckets: list[list[tuple[int, float]]] = [[] for _ in range(bins)]
    for y, s in zip(labels, scores):
        buckets[min(int(s * bins), bins - 1)].append((y, s))
    total = len(labels)
    return sum(
        len(b) / total * abs(sum(y for y, _ in b) / len(b) - sum(s for _, s in b) / len(b))
        for b in buckets
        if b
    )


SYNTHETIC_FLOOR_AUROC = 0.90      # the synthetic set is easy: a judge below this is out
SYNTHETIC_FLOOR_ACCURACY = 0.85
SYNTHETIC_MIN_PER_LANGUAGE = 10


def _by_language(rows: Sequence[dict[str, Any]], labels: Sequence[int], scores: Sequence[float]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for lang in LANGUAGES:
        idx = [i for i, r in enumerate(rows) if r.get("language") == lang]
        l = [labels[i] for i in idx]
        s = [scores[i] for i in idx]
        out[lang] = {"n": len(idx), "accuracy": accuracy(l, s) if idx else None, "auroc": auroc(l, s)}
    return out


def calibration_report(
    rows: Sequence[dict[str, Any]],
    scores: Sequence[float],
    *,
    baseline_scores: Optional[Sequence[float]] = None,
    judge: str = "",
) -> dict[str, Any]:
    """Calibration report with a verdict.

    The VERDICT is computed on REAL rows only (synthetic != true): synthetic rows
    are true by construction and easy, so they can run as a floor check but must
    never count toward the 30-per-language needed to call a judge trustworthy.
    """
    labels = [int(r["label"]) for r in rows]
    real = [i for i, r in enumerate(rows) if not r.get("synthetic")]
    synth = [i for i, r in enumerate(rows) if r.get("synthetic")]

    def pick(idx: list[int], seq: Sequence[Any]) -> list[Any]:
        return [seq[i] for i in idx]

    report: dict[str, Any] = {
        "judge": judge,
        "n": len(rows),
        "n_real": len(real),
        "n_synthetic": len(synth),
        "auroc": auroc(labels, scores),            # all rows, informational
        "accuracy": accuracy(labels, scores),
        "ece": ece(labels, scores),
    }
    if baseline_scores is not None:
        report["baseline_auroc"] = auroc(labels, baseline_scores)

    # Synthetic floor.
    if synth:
        s_rows, s_labels, s_scores = pick(synth, rows), pick(synth, labels), pick(synth, scores)
        s_lang = _by_language(s_rows, s_labels, s_scores)
        s_auroc = auroc(s_labels, s_scores)
        enough = all(s_lang[l]["n"] >= SYNTHETIC_MIN_PER_LANGUAGE for l in LANGUAGES)
        floor_problems: list[str] = []
        if enough:
            if s_auroc is None or s_auroc < SYNTHETIC_FLOOR_AUROC:
                floor_problems.append((f"synthetic AUROC {s_auroc} < {SYNTHETIC_FLOOR_AUROC}" if s_auroc is not None else "synthetic AUROC undefined (one label only)"))
            floor_problems += [f"synthetic {l} accuracy {s_lang[l]['accuracy']:.2f} < {SYNTHETIC_FLOOR_ACCURACY}"
                               for l in LANGUAGES if (s_lang[l]["accuracy"] or 0) < SYNTHETIC_FLOOR_ACCURACY]
        report["synthetic"] = {
            "n": len(synth), "auroc": s_auroc, "ece": ece(s_labels, s_scores), "by_language": s_lang,
            "floor": ("not_run" if not enough else "fail" if floor_problems else "pass"),
            "floor_reasons": floor_problems,
        }

    # Verdict on real rows only.
    r_rows, r_labels, r_scores = pick(real, rows), pick(real, labels), pick(real, scores)
    report["by_language"] = _by_language(r_rows, r_labels, r_scores)
    report["real_auroc"] = auroc(r_labels, r_scores)
    report["real_ece"] = ece(r_labels, r_scores)
    short = [f"{lang} has {report['by_language'][lang]['n']} (need {MIN_PER_LANGUAGE})"
             for lang in LANGUAGES if report["by_language"][lang]["n"] < MIN_PER_LANGUAGE]
    if short:
        report["verdict"] = "insufficient_data"
        report["reasons"] = ["too few human-labelled real examples to certify: " + "; ".join(short)]
        return report

    problems: list[str] = []
    if report["real_auroc"] is None or report["real_auroc"] < AUROC_MIN:
        problems.append((f"overall AUROC {report['real_auroc']} < {AUROC_MIN}" if report["real_auroc"] is not None else "overall AUROC undefined (all real rows share one label)"))
    if report["real_ece"] > ECE_MAX:
        problems.append(f"ECE {report['real_ece']:.3f} > {ECE_MAX}")
    for lang in LANGUAGES:
        acc = report["by_language"][lang]["accuracy"]
        if acc is None or acc < ACCURACY_MIN:
            problems.append(f"{lang} accuracy {acc} < {ACCURACY_MIN}")
    if baseline_scores is not None:
        base = auroc(r_labels, pick(real, baseline_scores))
        report["real_baseline_auroc"] = base
        if base is not None and report["real_auroc"] is not None and report["real_auroc"] < base + BASELINE_MARGIN:
            problems.append(f"AUROC {report['real_auroc']:.3f} does not beat the lexical baseline {base:.3f} by {BASELINE_MARGIN}")
    report["verdict"] = "not_trustworthy" if problems else "trustworthy"
    report["reasons"] = problems
    return report
