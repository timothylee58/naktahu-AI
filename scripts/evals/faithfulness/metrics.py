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


def calibration_report(
    rows: Sequence[dict[str, Any]],
    scores: Sequence[float],
    *,
    baseline_scores: Optional[Sequence[float]] = None,
    judge: str = "",
) -> dict[str, Any]:
    labels = [int(r["label"]) for r in rows]
    report: dict[str, Any] = {
        "judge": judge,
        "n": len(rows),
        "auroc": auroc(labels, scores),
        "accuracy": accuracy(labels, scores),
        "ece": ece(labels, scores),
        "by_language": {},
    }
    for lang in LANGUAGES:
        idx = [i for i, r in enumerate(rows) if r.get("language") == lang]
        l = [labels[i] for i in idx]
        s = [scores[i] for i in idx]
        report["by_language"][lang] = {"n": len(idx), "accuracy": accuracy(l, s) if idx else None, "auroc": auroc(l, s)}
    if baseline_scores is not None:
        report["baseline_auroc"] = auroc(labels, baseline_scores)

    short = [f"{lang} has {report['by_language'][lang]['n']} (need {MIN_PER_LANGUAGE})"
             for lang in LANGUAGES if report["by_language"][lang]["n"] < MIN_PER_LANGUAGE]
    if short:
        report["verdict"] = "insufficient_data"
        report["reasons"] = ["too few labelled examples to certify: " + "; ".join(short)]
        return report

    problems: list[str] = []
    if report["auroc"] is None or report["auroc"] < AUROC_MIN:
        problems.append(f"overall AUROC {report['auroc']} < {AUROC_MIN}")
    if report["ece"] > ECE_MAX:
        problems.append(f"ECE {report['ece']:.3f} > {ECE_MAX}")
    for lang in LANGUAGES:
        acc = report["by_language"][lang]["accuracy"]
        if acc is None or acc < ACCURACY_MIN:
            problems.append(f"{lang} accuracy {acc} < {ACCURACY_MIN}")
    base = report.get("baseline_auroc")
    if base is not None and report["auroc"] is not None and report["auroc"] < base + BASELINE_MARGIN:
        problems.append(f"AUROC {report['auroc']:.3f} does not beat the lexical baseline {base:.3f} by {BASELINE_MARGIN}")
    report["verdict"] = "not_trustworthy" if problems else "trustworthy"
    report["reasons"] = problems
    return report
