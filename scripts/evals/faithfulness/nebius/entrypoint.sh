#!/usr/bin/env bash
# Container entrypoint for the faithfulness-judge calibration job.
#
# Runs on CPU. It does NOT host the model: it calls a JEV-27B-VL server over
# JEV_URL (a separate GPU workload, see README.md). Output: a JSON report in
# $OUT_DIR (always written; default /out). stdout also carries the JSON followed by a
# final "VERDICT: ..." line, so it is not pure JSON: read the report file instead.
#
# Env:
#   JUDGE                  jev (default) | lexical (no server needed; baseline only)
#   JEV_URL                base URL of the model server (required for JUDGE=jev)
#   JEV_API_KEY            optional bearer token
#   REAL_CASES             path to the human-labelled JSONL (default /data/real_cases.jsonl, optional)
#   OUT_DIR                where to write report-<utc timestamp>-<pid>-<random>.json (default /out)
#   FAIL_UNLESS_TRUSTWORTHY  "1" => exit 1 unless the verdict is trustworthy AND the synthetic floor passes
set -euo pipefail

JUDGE="${JUDGE:-jev}"
REAL_CASES="${REAL_CASES:-/data/real_cases.jsonl}"
OUT_DIR="${OUT_DIR:-/out}"
DATA="scripts/evals/faithfulness/data"
CASES=("$DATA/calibration_seed.jsonl" "$DATA/calibration_synthetic.jsonl")

if [[ -f "$REAL_CASES" ]]; then
  echo "validating human-labelled set: $REAL_CASES" >&2
  python3 -m scripts.evals.faithfulness.pilot validate --cases "$REAL_CASES" >&2   # exit 2 unreadable/malformed input, 1 structural problems
  CASES+=("$REAL_CASES")
else
  echo "no human-labelled set at $REAL_CASES: only the synthetic floor can run; the verdict will be insufficient_data" >&2
fi

mkdir -p "$OUT_DIR"
REPORT="$OUT_DIR/report-$(date -u +%Y%m%dT%H%M%SZ)-$$-$RANDOM.json"
ARGS=(calibrate --cases "${CASES[@]}" --judge "$JUDGE" --report "$REPORT")
[[ "${FAIL_UNLESS_TRUSTWORTHY:-0}" == "1" ]] && ARGS+=(--fail-unless-trustworthy)

python3 -m scripts.evals.faithfulness.pilot "${ARGS[@]}"
echo "report written to $REPORT" >&2
