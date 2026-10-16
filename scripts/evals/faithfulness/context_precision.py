"""Context precision, as RAGAS defines it (the variant that uses the answer as the reference).

For one sample the retrieved chunks, in rank order, are each judged useful or not
(r_k). Precision@k is the share of the first k chunks that are useful, and

    context_precision = sum_k(precision@k * r_k) / (number of useful chunks)

so a useful chunk ranked first scores higher than the same chunk ranked fifth. A
sample whose chunks are all judged not useful scores 0. The run's score is the mean
over samples. Like faithfulness it refuses to emit a number if too many judgements
failed.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any, Sequence

from scripts.evals.faithfulness.judge import JudgeError
from scripts.evals.faithfulness.scoring import MAX_ERROR_RATE, WORKERS, ScoreRefused

USEFUL_AT = 0.5


def context_precision(flags: Sequence[bool]) -> float:
    useful = sum(1 for f in flags if f)
    if useful == 0:
        return 0.0
    hits, total = 0, 0.0
    for k, flag in enumerate(flags, start=1):
        if flag:
            hits += 1
            total += hits / k
    return total / useful


def score_context_precision(samples: Sequence[dict[str, Any]], judge: Any, *, workers: int = WORKERS) -> dict[str, Any]:
    if not hasattr(judge, "p_relevant"):
        raise ScoreRefused(f"judge '{getattr(judge, 'name', '?')}' cannot judge chunk relevance")
    jobs: list[tuple[int, int, str, str, str]] = []
    for i, sample in enumerate(samples):
        for k, chunk in enumerate(sample.get("contexts") or []):
            jobs.append((i, k, sample.get("question", ""), sample.get("answer", ""), str(chunk)))

    def _judge(job: tuple[int, int, str, str, str]) -> tuple[int, int, float | None]:
        i, k, question, answer, chunk = job
        try:
            return i, k, judge.p_relevant(question=question, answer=answer, chunk=chunk)
        except JudgeError:
            return i, k, None

    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(_judge, jobs))

    errors = sum(1 for _, _, p in results if p is None)
    if results and errors / len(results) > MAX_ERROR_RATE:
        raise ScoreRefused(f"{errors} of {len(results)} chunks could not be judged (> {MAX_ERROR_RATE:.0%}); no score emitted")

    per_sample: dict[int, dict[int, bool]] = {}
    for i, k, p in results:
        if p is not None:
            per_sample.setdefault(i, {})[k] = p >= USEFUL_AT
    if not per_sample:
        raise ScoreRefused("no chunks were judged; no score emitted")

    scores: dict[int, float] = {}
    for i, by_rank in per_sample.items():
        scores[i] = context_precision([by_rank[k] for k in sorted(by_rank)])
    by_language: dict[str, list[float]] = {}
    for i, s in scores.items():
        by_language.setdefault(str(samples[i].get("language") or "unknown"), []).append(s)
    return {
        "context_precision": round(sum(scores.values()) / len(scores), 4),
        "context_precision_by_language": {k: round(sum(v) / len(v), 4) for k, v in sorted(by_language.items())},
        "context_precision_samples": len(scores),
        "chunk_errors": errors,
    }
