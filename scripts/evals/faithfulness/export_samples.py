"""Run the real NakTahu pipeline over a question set and export what the judge needs.

For each question it runs the compiled LangGraph (router -> guard -> rag -> analyst
-> synthesiser), then writes one JSONL row: {id, language, question, answer,
contexts}. `contexts` are the chunks the pipeline kept after analyst_node, in rank
order, capped at --top-k, because those are what the answer was written from.

Questions that produce no answer to judge are skipped and COUNTED, never hidden:
blocked queries, clarification prompts, and answers with no retrieved chunks. A
faithfulness number over only the questions the system was confident about would be
flattering, so the skip counts are written next to the samples (<out>.meta.json) and
printed in the CI summary.

Run it as a FILE from the repo root, with apps/api on PYTHONPATH and the production env
vars set (SUPABASE_*, ILMU_*, an embedding key). Not `python -m scripts...`: apps/api also
has a package called `scripts`, and running as a file keeps the two from shadowing each
other (this module deliberately imports nothing from `scripts.*`):

    PYTHONPATH=apps/api python scripts/evals/faithfulness/export_samples.py \
        --questions apps/api/evals/answer_quality.jsonl apps/api/evals/language_accuracy.jsonl \
        --out samples.jsonl
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Optional, Sequence

MIN_SAMPLES = 10


def load_questions(paths: Sequence[str | Path], limit: Optional[int] = None) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for path in paths:
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            query = str(row.get("query", "")).strip()
            if query and query not in seen:
                seen.add(query)
                out.append({"query": query, "source": Path(path).name})
    return out[:limit] if limit else out


def skip_reason(result: dict[str, Any]) -> Optional[str]:
    if result.get("error"):
        return "blocked_or_error"
    if not (result.get("streaming_token_buffer") or "").strip():
        return "no_answer"
    if not result.get("retrieved_chunks"):
        return "no_retrieved_chunks"
    if result.get("needs_clarification"):
        return "clarification"
    return None


def to_sample(index: int, question: dict[str, Any], result: dict[str, Any], top_k: int) -> dict[str, Any]:
    chunks = list(result.get("retrieved_chunks") or [])[:top_k]
    return {
        "id": f"q{index:03d}",
        "language": result.get("language") or "unknown",
        "question": question["query"],
        "answer": (result.get("streaming_token_buffer") or "").strip(),
        "contexts": [getattr(c, "content", None) or c.get("content", "") for c in chunks],
        "source_file": question["source"],
    }


async def export(questions: Sequence[dict[str, Any]], graph: Any, *, top_k: int = 5, concurrency: int = 3) -> tuple[list[dict[str, Any]], Counter]:
    sem = asyncio.Semaphore(concurrency)
    skipped: Counter = Counter()
    samples: list[Optional[dict[str, Any]]] = [None] * len(questions)

    async def one(i: int, q: dict[str, Any]) -> None:
        async with sem:
            try:
                result = await graph.ainvoke({"query": q["query"], "session_id": f"rag-eval-{i}", "user_id": None})
            except Exception as exc:   # one bad question must not sink the run
                skipped[f"pipeline_error:{type(exc).__name__}"] += 1
                return
        reason = skip_reason(result)
        if reason:
            skipped[reason] += 1
        else:
            samples[i] = to_sample(i, q, result, top_k)

    await asyncio.gather(*(one(i, q) for i, q in enumerate(questions)))
    return [s for s in samples if s is not None], skipped


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Export pipeline answers and contexts for the faithfulness run")
    parser.add_argument("--questions", nargs="+", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--concurrency", type=int, default=3)
    args = parser.parse_args(argv)

    from app.agents.graph import build_graph   # needs apps/api on PYTHONPATH and live credentials

    questions = load_questions(args.questions, args.limit)
    graph = build_graph().compile()
    samples, skipped = asyncio.run(export(questions, graph, top_k=args.top_k, concurrency=args.concurrency))

    out = Path(args.out)
    out.write_text("".join(json.dumps(s, ensure_ascii=False) + "\n" for s in samples), encoding="utf-8")
    meta = {
        "questions": len(questions),
        "exported": len(samples),
        "skipped": dict(skipped),
        "exported_by_language": dict(Counter(s["language"] for s in samples)),
        "top_k": args.top_k,
    }
    out.with_suffix(".meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(json.dumps(meta, indent=2))
    if len(samples) < MIN_SAMPLES:
        print(f"ERROR: only {len(samples)} usable samples (need at least {MIN_SAMPLES}); a score over so few means nothing", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
