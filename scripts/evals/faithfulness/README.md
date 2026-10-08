# Faithfulness-judge pilot

**Why this exists.** The deploy gate (`scripts/evals/run_eval_gate.py`) has a
faithfulness threshold of 0.75, but nothing in this repo computes the score; the
CI run prints `NOT MEASURED`. This pilot is the missing measurement: a judge that
returns, per claim in an answer, the probability the retrieved context supports it.

**Status: scaffold. Nothing here has been run against a real model.** The
sandbox this was built in has no GPU and no route to Hugging Face. What *is*
tested (30 tests, with the model call replaced by a mock transport) is everything
around the model: claim splitting, the request/response handling, the metrics,
the verdict logic, and the hand-off to the deploy gate.

## Pieces

| file | role |
|---|---|
| `claims.py` | answer → claims (one per sentence; EN/BM/ZH punctuation). Coarser than RAGAS's atomic decomposition, so it can understate unfaithfulness. |
| `judge.py` | `LexicalOverlapJudge` (baseline) and `JevDecideJudge` (calls a self-hosted `autotrust/JEV-27B-VL` `POST /v1/decide`). |
| `metrics.py` | AUROC, ECE, accuracy, and the **verdict**: `trustworthy` / `not_trustworthy` / `insufficient_data`. |
| `scoring.py` | per-sample supported-claim ratio, averaged; **refuses** to emit a score if >10% of claims could not be judged. |
| `pilot.py` | CLI: `calibrate` and `score`. |
| `data/calibration_seed.jsonl` | 18 **synthetic** labelled claims (6 per language, fictional programmes). Plumbing only. |

## Running it

```bash
# 1. Is the judge any good? (JEV_URL = base URL of the model server)
JEV_URL=http://<host>:8000 python -m scripts.evals.faithfulness.pilot calibrate \
    --cases <your labelled set>.jsonl --judge jev --report report.json

# 2. Produce the number the deploy gate reads
JEV_URL=http://<host>:8000 python -m scripts.evals.faithfulness.pilot score \
    --samples samples.jsonl --judge jev --out scores.json
python -m scripts.evals.run_eval_gate --scores-json scores.json
```

Calibration case: `{"id","language":"bm|en|zh","context","claim","label":1|0}`.
Score sample: `{"id","language","question","answer","contexts":[...]}`.
Optional `JEV_API_KEY` is sent as a Bearer token if set.

## What would make the judge trustworthy

`calibrate` returns `trustworthy` only if **all** hold, on at least 30 human-labelled
examples *per language*: overall AUROC ≥ 0.85, ECE ≤ 0.15, accuracy ≥ 0.80 in each
of bm/en/zh, and AUROC at least 0.05 above the lexical baseline. The bundled seed
set can only ever return `insufficient_data` (it is 18 synthetic rows). Its paraphrased
"supported" claims are deliberate: they push the lexical baseline to ≈0.56 AUROC, so a
real judge has to prove it does better than counting shared words.

The model card for `autotrust/JEV-27B-VL` lists **English only** and reports its
benchmarks itself; nothing about Malay or Mandarin is assumed here. That is what the
per-language gate is for.

## Not done yet

- **Real calibration data.** 90+ examples (30 each of bm/en/zh) labelled by a person from
  real pipeline answers, including hard negatives (wrong number, wrong entity, plausible
  unsupported addition).
- **An exporter** that runs the live pipeline over a question set and writes the
  `score` sample file. Nothing in the repo produces it today.
- **Hosting.** The model card asks for a ≥80 GB GPU, a development build of vLLM and
  `--max-num-seqs 8`, and ships its own `serve_decide.py` (review that code before running
  it). Packaging this as a Nebius job is not done: Nebius's job-submission syntax has not
  been checked against its docs, so none is guessed here. There is deliberately **no
  cron** for this pilot: GitHub-hosted runners have no GPU.
- **A live smoke test** of `JevDecideJudge` against a real server. The request and
  response shapes come from the model card.
