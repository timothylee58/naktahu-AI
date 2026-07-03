"""Deploy eval gate: faithfulness (existing) + temporal_accuracy (new).

Faithfulness only measures answer-to-chunk consistency, so a stale chunk
reproduced perfectly passes it while being factually wrong. This harness adds a
second gate — average temporal_accuracy (chunk currency) — and records both to
the ``eval_runs`` table so deploys can be gated and tracked over time.

    if scores["faithfulness"] < 0.7:        # existing gate
        sys.exit(1)
    if scores["temporal_accuracy"] < 0.6:   # new freshness gate
        sys.exit(1)

temporal_accuracy is computed here (deterministic, offline) from a golden
samples file. faithfulness is read from --faithfulness / FAITHFULNESS_SCORE /
--scores-json (produced by a live RAGAS run, which needs LLM credentials); when
it is not supplied, its gate is skipped unless --require-faithfulness is set, so
credential-free CI still enforces the temporal gate.

Usage:
    PYTHONPATH=. python -m scripts.evals.run_eval_gate \
        --samples scripts/evals/data/temporal_golden.jsonl
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Optional

from scripts.evals.temporal_scorer import (
    TEMPORAL_ACCURACY_GATE,
    aggregate_temporal_accuracy,
)

FAITHFULNESS_GATE = 0.7

# name -> minimum passing score
GATES: dict[str, float] = {
    "faithfulness": FAITHFULNESS_GATE,
    "temporal_accuracy": TEMPORAL_ACCURACY_GATE,
}

_DEFAULT_SAMPLES = Path(__file__).parent / "data" / "temporal_golden.jsonl"


def load_samples(path: str | Path) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                samples.append(json.loads(line))
    return samples


def _sample_chunks_to_meta(sample: dict[str, Any], today: date) -> list[dict[str, Any]]:
    """Convert a golden sample's relative-dated chunks into scorer input.

    Chunks use ``effective_days_ago`` (relative, so the fixture never ages out)
    which is resolved against ``today``; ``null`` means unknown effective date.
    """
    meta: list[dict[str, Any]] = []
    for chunk in sample.get("chunks", []):
        days_ago = chunk.get("effective_days_ago")
        effective_date = (today - timedelta(days=days_ago)).isoformat() if days_ago is not None else None
        meta.append({
            "effective_date": effective_date,
            "superseded_by": chunk.get("superseded_by"),
        })
    return meta


def compute_avg_temporal_accuracy(
    samples: list[dict[str, Any]], *, today: Optional[date] = None
) -> float:
    """Mean per-sample temporal_accuracy (each sample = worst chunk)."""
    ref = today or date.today()
    if not samples:
        return 0.0
    per_sample = [
        aggregate_temporal_accuracy(
            _sample_chunks_to_meta(sample, ref),
            domain=sample.get("domain"),
            today=ref,
        )
        for sample in samples
    ]
    return round(sum(per_sample) / len(per_sample), 4)


def resolve_faithfulness(args: argparse.Namespace) -> Optional[float]:
    """Faithfulness from --faithfulness, then --scores-json, then env."""
    if args.faithfulness is not None:
        return float(args.faithfulness)
    if args.scores_json:
        data = json.loads(Path(args.scores_json).read_text(encoding="utf-8"))
        if data.get("faithfulness") is not None:
            return float(data["faithfulness"])
    env = os.environ.get("FAITHFULNESS_SCORE")
    if env not in (None, ""):
        return float(env)
    return None


def evaluate_gates(
    scores: dict[str, Optional[float]], *, require: tuple[str, ...] = ()
) -> tuple[list[str], list[str]]:
    """Return (failures, skipped). A gate whose score is None is skipped unless
    it is in ``require`` (then it's a failure)."""
    failures: list[str] = []
    skipped: list[str] = []
    for name, threshold in GATES.items():
        value = scores.get(name)
        if value is None:
            if name in require:
                failures.append(f"{name}: no score provided (required)")
            else:
                skipped.append(name)
            continue
        if value < threshold:
            failures.append(f"{name} {value:.3f} < {threshold}")
    return failures, skipped


def _git_sha() -> Optional[str]:
    sha = os.environ.get("GITHUB_SHA")
    if sha:
        return sha
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        return None


def record_eval_run(
    scores: dict[str, Optional[float]], passed: bool, notes: str = ""
) -> bool:
    """Best-effort insert into eval_runs. Skips (returns False) when Supabase
    credentials are absent or the client is unavailable; never raises."""
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print("eval_runs: SUPABASE creds not set — skipping DB record")
        return False
    try:
        from supabase import create_client  # lazy: harness stays dep-free otherwise

        client = create_client(url, key)
        client.table("eval_runs").insert({
            "git_sha": _git_sha(),
            "faithfulness": scores.get("faithfulness"),
            "avg_temporal_accuracy": scores.get("avg_temporal_accuracy"),
            "passed": passed,
            "scores": {k: v for k, v in scores.items() if v is not None},
            "notes": notes or None,
        }).execute()
        print("eval_runs: recorded run")
        return True
    except Exception as exc:  # noqa: BLE001 - recording must never fail the gate
        print(f"eval_runs: record failed (non-fatal): {exc}")
        return False


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Deploy eval gate")
    parser.add_argument("--samples", default=str(_DEFAULT_SAMPLES))
    parser.add_argument("--faithfulness", type=float, default=None)
    parser.add_argument("--scores-json", default=None)
    parser.add_argument("--require-faithfulness", action="store_true")
    parser.add_argument("--no-record", action="store_true")
    args = parser.parse_args(argv)

    samples = load_samples(args.samples)
    avg_temporal = compute_avg_temporal_accuracy(samples)
    faithfulness = resolve_faithfulness(args)

    scores: dict[str, Optional[float]] = {
        "avg_temporal_accuracy": avg_temporal,
        # gate key mirrors the user-facing snippet / GATES map
        "temporal_accuracy": avg_temporal,
        "faithfulness": faithfulness,
    }

    require = ("faithfulness",) if args.require_faithfulness else ()
    failures, skipped = evaluate_gates(scores, require=require)
    passed = not failures

    print("── eval gate ──")
    print(f"  samples:              {len(samples)}")
    print(f"  avg_temporal_accuracy {avg_temporal:.3f}  (gate ≥ {TEMPORAL_ACCURACY_GATE})")
    fv = f"{faithfulness:.3f}" if faithfulness is not None else "n/a"
    print(f"  faithfulness          {fv}  (gate ≥ {FAITHFULNESS_GATE})")
    for name in skipped:
        print(f"  skipped gate: {name} (no score provided)")

    if not args.no_record:
        record_eval_run(scores, passed, notes=", ".join(failures))

    if failures:
        print("GATE FAILED: " + "; ".join(failures))
        return 1
    print("GATE PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
