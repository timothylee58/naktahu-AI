"""Faithfulness-judge pilot CLI.

    # Can this judge be trusted? (needs JEV_URL for --judge jev)
    python -m scripts.evals.faithfulness.pilot calibrate \
        --cases scripts/evals/faithfulness/data/calibration_seed.jsonl --judge jev --report report.json

    # Produce the number the deploy gate reads
    python -m scripts.evals.faithfulness.pilot score --samples samples.jsonl --judge jev --out scores.json
    python -m scripts.evals.run_eval_gate --scores-json scores.json

`calibrate` always also runs the lexical baseline, and prints a verdict:
trustworthy / not_trustworthy / insufficient_data. The bundled seed set is
synthetic and tiny, so it can only ever say "insufficient_data": it proves the
plumbing, not the judge. Certifying a judge needs >= 30 human-labelled examples
per language (bm, en, zh) drawn from real pipeline outputs.

Sample file (`score`): JSONL of {"id", "language", "question", "answer", "contexts": [str, ...]}.
Nothing in this repo exports those yet; producing them from the live pipeline is
the next step.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional

from scripts.evals.faithfulness.judge import JudgeError, LexicalOverlapJudge, make_judge
from scripts.evals.faithfulness.metrics import calibration_report
from scripts.evals.faithfulness.scoring import ScoreRefused, score_samples
from scripts.evals.faithfulness.validate import validate_cases


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    return [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]


def run_calibration(rows: list[dict[str, Any]], judge: Any) -> dict[str, Any]:
    baseline = LexicalOverlapJudge()
    scores: list[float] = []
    base_scores: list[float] = []
    for r in rows:
        scores.append(judge.p_supported(context=r["context"], claim=r["claim"]))
        base_scores.append(baseline.p_supported(context=r["context"], claim=r["claim"]))
    return calibration_report(rows, scores, baseline_scores=base_scores, judge=judge.name)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Faithfulness judge pilot")
    sub = parser.add_subparsers(dest="cmd", required=True)
    cal = sub.add_parser("calibrate")
    cal.add_argument("--cases", required=True, nargs="+", help="one or more JSONL files (synthetic and/or human-labelled)")
    cal.add_argument("--judge", choices=["jev", "lexical"], default="lexical")
    cal.add_argument("--report", default=None)
    cal.add_argument("--fail-unless-trustworthy", action="store_true")
    val = sub.add_parser("validate", help="check a human-labelled calibration file")
    val.add_argument("--cases", required=True, nargs="+")
    val.add_argument("--require-complete", action="store_true", help="also fail unless every language has the 30 real rows needed")
    sc = sub.add_parser("score")
    sc.add_argument("--samples", required=True)
    sc.add_argument("--judge", choices=["jev", "lexical"], default="jev")
    sc.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    if args.cmd == "validate":
        try:
            rows = [r for path in args.cases for r in load_jsonl(path)]
        except (OSError, ValueError) as exc:   # JSONDecodeError is a ValueError
            print(f"ERROR: cannot read {args.cases}: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 2
        problems, progress = validate_cases(rows)
        for line in problems:
            print(f"PROBLEM: {line}")
        print("real rows per language (have/need): " + ", ".join(f"{k} {v}" for k, v in progress.items()))
        incomplete = any(int(v.split("/")[0]) < int(v.split("/")[1]) for v in progress.values())
        if problems or (args.require_complete and incomplete):
            return 1
        print("OK" + (" (not yet enough real rows to certify a judge)" if incomplete else ""))
        return 0

    try:
        judge = make_judge(args.judge)
        if args.cmd == "calibrate":
            report = run_calibration([r for path in args.cases for r in load_jsonl(path)], judge)
            print(json.dumps(report, indent=2, ensure_ascii=False))
            if args.report:
                Path(args.report).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"VERDICT: {report['verdict']}")
            # Strict mode also honours the synthetic floor, so a judge that fails even the
            # easy by-construction rows can never pass the build on real rows alone.
            if args.fail_unless_trustworthy:
                if report["verdict"] != "trustworthy":
                    return 1
                if report.get("synthetic", {}).get("floor") == "fail":
                    print("ERROR: judge fails the synthetic floor: " + "; ".join(report["synthetic"].get("floor_reasons", [])), file=sys.stderr)
                    return 1
            return 0
        result = score_samples(load_jsonl(args.samples), judge)
        Path(args.out).write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result, indent=2))
        return 0
    except (JudgeError, ScoreRefused) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
