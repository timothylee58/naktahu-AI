# Running the calibration as a Nebius job

**Status: written but not run.** The image has not been built (no Docker daemon in
the sandbox this was written in) and nothing here has touched Nebius. Each fact
below is marked **[docs]** (found in Nebius's published docs via search, not
re-checked against your CLI version) or **[unverified]**.

## Two separate workloads

| | what | hardware | in this repo |
|---|---|---|---|
| **A. model server** | `autotrust/JEV-27B-VL` behind `POST /v1/decide` | one GPU with 80 GB+ | **not packaged**: use the model card's `serve.sh` |
| **B. calibration runner** | this directory: validates the labelled set, calls A, writes a report | CPU only | `Dockerfile` + `entrypoint.sh` |

They are separate on purpose. The server needs a development build of vLLM and a
GPU; the runner needs only Python and `httpx`, so it can be rebuilt and re-run
cheaply while the model server stays up.

### A. The model server (per the model card, **[unverified]** here)
`hf download autotrust/JEV-27B-VL --local-dir JEV-27B-VL`, then `bash JEV-27B-VL/serve.sh`
(vLLM on :8000). Required by the card: `--max-num-seqs 8`; on an 80 GB GPU start with
`MAX_MODEL_LEN=131072`. It ships its own `serve_decide.py`: **read it before you run it**.
Its language list is English only, so the calibration set below is what tells you whether
Malay and Mandarin work.

### B. The runner image
```bash
docker build -f scripts/evals/faithfulness/nebius/Dockerfile -t naktahu-faithfulness-pilot .
mkdir -p out && docker run --rm -e JUDGE=lexical -v "$PWD/out:/out" naktahu-faithfulness-pilot   # smoke test, no model
```
Env: `JUDGE` (`jev` default | `lexical`), `JEV_URL`, `JEV_API_KEY` (optional),
`REAL_CASES` (default `/data/real_cases.jsonl`, optional), `OUT_DIR` (default `/out`),
`FAIL_UNLESS_TRUSTWORTHY=1` to make a non-certified judge a failing exit code.
Exit codes: 0 report written; 1 malformed labelled set or strict-mode failure; 2 judge unreachable/unset.
The entrypoint was run locally on all three paths (report, strict failure, missing `JEV_URL`).

## Submitting it to Nebius Serverless Jobs
**[docs]** `nebius ai job create` runs a container image as a one-off or scheduled batch job.
It accepts `--container-command`, `--args` and repeatable `--env KEY=VALUE`; a platform and
preset are required and must match each other; `nebius ai job list` shows jobs; volumes come
in a `source:container_path[:mode]` form and an `s3://bucket:/container_path[:mode[:profile]]`
form; the CLI is in beta. **[unverified]** the exact flag names for the job name, image,
platform, preset, timeout and volume on `create`. Confirm with `nebius ai job create --help`
before using this skeleton:

```bash
nebius ai job create \
  --name faithfulness-calibration \
  --image <registry>/naktahu-faithfulness-pilot:<tag> \
  --platform <cpu platform> --preset <cpu preset> \
  --env JUDGE=jev --env JEV_URL=http://<model server>:8000 \
  --env FAIL_UNLESS_TRUSTWORTHY=0 \
  --volume s3://<bucket>:/out:rw \
  --volume s3://<labelled-bucket>:/data:ro   `# must contain real_cases.jsonl; without it only the synthetic floor runs`
```
Push the image to a registry the job can pull from first; that step is also yours.

## What you still have to supply
1. **The human-labelled set.** `calibrate` can only certify a judge from real rows:
   - Format: one JSON object per line: e.g. `{"id":"case-001","language":"en","context":"...","claim":"...","label":1,"labeller":"<who>"}` (`language` is bm, en or zh; `label` is the integer 1 = supported, 0 = not).
   - Need >= 30 per language, 30-70% supported claims per language, hard negatives
     (wrong number, wrong entity, plausible but unsupported addition).
   - Take contexts and claims from real pipeline answers, not from this repo's templates.
   - Check it first: `python -m scripts.evals.faithfulness.pilot validate --cases real_cases.jsonl --require-complete`
2. **A model server** (A) and a registry for the image.
3. **A decision** on what to do if the verdict is `not_trustworthy`: keep `FAITHFULNESS_SCORE` unset (the gate then says `NOT MEASURED`) rather than gate on a judge that failed.
