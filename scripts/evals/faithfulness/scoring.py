"""Claim-level faithfulness over a set of (question, answer, contexts) samples.

faithfulness(sample) = supported claims / judged claims, as RAGAS defines it
(with sentence-level claims, see claims.py); the run's score is the mean over
samples. The output JSON has a top-level "faithfulness" key, which is exactly
what ``scripts.evals.run_eval_gate --scores-json`` reads.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any, Sequence

from scripts.evals.faithfulness.claims import split_claims
from scripts.evals.faithfulness.judge import Judge, JudgeError

SUPPORTED_AT = 0.5
MAX_ERROR_RATE = 0.10     # beyond this the number is not trustworthy, so refuse to emit it
WORKERS = 8               # JEV-27B-VL needs --max-num-seqs 8; more just queue


class ScoreRefused(RuntimeError):
    """Too many claims could not be judged for the score to mean anything."""


def score_samples(samples: Sequence[dict[str, Any]], judge: Judge, *, workers: int = WORKERS) -> dict[str, Any]:
    jobs: list[tuple[int, str, str]] = []
    for i, sample in enumerate(samples):
        context = "\n\n---\n\n".join(str(c) for c in sample.get("contexts") or [])
        for claim in split_claims(sample.get("answer", "")):
            jobs.append((i, context, claim))

    def _judge(job: tuple[int, str, str]) -> tuple[int, float | None]:
        i, context, claim = job
        try:
            return i, judge.p_supported(context=context, claim=claim)
        except JudgeError:
            return i, None

    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(_judge, jobs))

    errors = sum(1 for _, p in results if p is None)
    if results and errors / len(results) > MAX_ERROR_RATE:
        raise ScoreRefused(f"{errors} of {len(results)} claims could not be judged (> {MAX_ERROR_RATE:.0%}); no score emitted")

    per_sample: dict[int, list[bool]] = {}
    for i, p in results:
        if p is not None:
            per_sample.setdefault(i, []).append(p >= SUPPORTED_AT)
    if not per_sample:
        raise ScoreRefused("no claims were judged; no score emitted")
    ratios = [sum(v) / len(v) for v in per_sample.values()]
    return {
        "faithfulness": round(sum(ratios) / len(ratios), 4),
        "judge": judge.name,
        "samples_scored": len(ratios),
        "samples_skipped": len(samples) - len(ratios),
        "claims_judged": len(results) - errors,
        "claim_errors": errors,
    }
