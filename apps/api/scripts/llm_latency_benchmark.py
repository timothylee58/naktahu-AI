#!/usr/bin/env python3
"""Benchmark streaming latency: Nemotron on Nebius Token Factory vs ILMU.

Sends the same prompts to each configured target and records, per call:

  ttft_any      seconds to the first streamed delta of any kind (content or reasoning)
  ttft_content  seconds to the first visible content token (what a user would see)
  total         seconds to the end of the stream
  tok_per_s     completion tokens / (total - ttft_any): decode speed once streaming starts

Completion tokens come from the provider's usage chunk when it sends one; otherwise
they are estimated from streamed characters (chars / 4) and the row is marked
"est". Comparing an estimate against a real count is misleading, so check the
"tokens" column before quoting tok_per_s.

Targets are read from the environment (names only; values are never printed):

  nemotron-fast       NEMOTRON_API_KEY, NEMOTRON_BASE_URL, NEMOTRON_FAST_MODEL
  nemotron-reasoning  NEMOTRON_API_KEY, NEMOTRON_BASE_URL, NEMOTRON_REASONING_MODEL
  ilmu                ILMU_API_KEY, ILMU_BASE_URL, ILMU_CHAT_MODEL
  (NEMOTRON_EXTRA_BODY, a JSON object, is passed through as extra_body, as in
   app/agents/eligibility_agent/llm_split.py.)

A target with any of its variables missing is skipped and listed as such.

    python -m scripts.llm_latency_benchmark --runs 5 --out bench.json   # from apps/api
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator, Optional

# Representative of the two real call shapes: a short structured extraction (intake)
# and a longer streamed summary. Generic wording; nothing here is user data.
PROMPTS: list[dict[str, str]] = [
    {
        "name": "intake-extraction",
        "system": "Extract the business profile as compact JSON with keys: business_type, sector, "
        "annual_revenue_rm, headcount, bumiputera_owned. Reply with JSON only.",
        "user": "Kami sebuah syarikat Sdn Bhd dalam sektor pembuatan makanan di Johor, "
        "hasil tahunan sekitar RM1.8 juta, 24 pekerja, dimiliki majoriti Bumiputera.",
    },
    {
        "name": "eligibility-summary",
        "system": "You summarise grant eligibility for a Malaysian SME in plain English. Use only "
        "the evidence given. State what matches, what is near-miss, and the next step. Be concise.",
        "user": "Profile: Sdn Bhd, food manufacturing, Johor, revenue RM1.8m, 24 staff, majority "
        "Bumiputera-owned. Evidence: Scheme A requires revenue under RM2.5m and 5-75 staff (match). "
        "Scheme B requires a manufacturing licence on file (not confirmed). Scheme C is for "
        "exporters only (no match). Scheme A and B can be combined.",
    },
]

_CHARS_PER_TOKEN = 4  # rough estimate when the provider sends no usage
_CALL_TIMEOUT_S = 45.0  # per request; keeps the worst case (every call hangs) inside the job budget
_MAX_RUNS = 30
_MAX_TOKENS_CEILING = 4096


@dataclass
class Sample:
    ttft_any: Optional[float] = None
    ttft_content: Optional[float] = None
    total: Optional[float] = None
    tokens: Optional[int] = None
    tokens_estimated: bool = False
    error: Optional[str] = None

    @property
    def tok_per_s(self) -> Optional[float]:
        if self.tokens is None or self.total is None or self.ttft_any is None:
            return None
        decode = self.total - self.ttft_any
        return self.tokens / decode if decode > 0 else None


@dataclass
class Target:
    name: str
    model: str
    api_key: str = field(repr=False)
    base_url: str
    extra_body: Optional[dict[str, Any]] = None


def percentile(values: list[float], pct: float) -> Optional[float]:
    """Linear-interpolated percentile (pct in 0..100); None for no data."""
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (pct / 100) * (len(ordered) - 1)
    lo, hi = math.floor(rank), math.ceil(rank)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (rank - lo)


async def measure_stream(chunks: AsyncIterator[Any], *, start: float, clock: Any = time.perf_counter) -> Sample:
    """Consume an OpenAI-style chunk stream and time it. `start` is the clock value
    taken just before the request was sent."""
    sample = Sample()
    content_chars = 0
    reasoning_chars = 0
    async for chunk in chunks:
        usage = getattr(chunk, "usage", None)
        if usage is not None and getattr(usage, "completion_tokens", None):
            sample.tokens = int(usage.completion_tokens)
        # The usage-only final chunk has no choices; indexing it raises (the same
        # trap as _stream_ilmu in the synthesiser), so skip it.
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        text = getattr(delta, "content", None) or ""
        thought = getattr(delta, "reasoning_content", None) or getattr(delta, "reasoning", None) or ""
        if not (text or thought):
            continue
        now = clock() - start
        if sample.ttft_any is None:
            sample.ttft_any = now
        if text and sample.ttft_content is None:
            sample.ttft_content = now
        content_chars += len(text)
        reasoning_chars += len(thought)
    sample.total = clock() - start
    if sample.ttft_any is None:
        # Headers and usage but no content or reasoning delta (a filtered or empty reply):
        # there is nothing to time, so it must not count as a successful sample.
        sample.error = "EmptyStream: no content or reasoning delta received"
        return sample
    if sample.tokens is None and (content_chars or reasoning_chars):
        sample.tokens = max(1, (content_chars + reasoning_chars) // _CHARS_PER_TOKEN)
        sample.tokens_estimated = True
    return sample


def summarise(samples: list[Sample]) -> dict[str, Any]:
    """p50/p95 over successful samples, plus counts. Errors are counted, never averaged in."""
    ok = [s for s in samples if s.error is None and s.total is not None]

    def col(get: Any) -> list[float]:
        return [v for v in (get(s) for s in ok) if v is not None]

    def pair(values: list[float]) -> dict[str, Optional[float]]:
        return {"p50": percentile(values, 50), "p95": percentile(values, 95)}

    return {
        "ok": len(ok),
        "errors": len(samples) - len(ok),
        "ttft_any": pair(col(lambda s: s.ttft_any)),
        "ttft_content": pair(col(lambda s: s.ttft_content)),
        "total": pair(col(lambda s: s.total)),
        "tok_per_s": pair(col(lambda s: s.tok_per_s)),
        "tokens_estimated": any(s.tokens_estimated for s in ok),
    }


def load_targets(env: dict[str, str]) -> tuple[list[Target], list[str]]:
    """Targets whose variables are all set, and the names (with what is missing) of those skipped."""
    extra: Optional[dict[str, Any]] = None
    raw = (env.get("NEMOTRON_EXTRA_BODY") or "").strip()
    if raw:
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise ValueError("NEMOTRON_EXTRA_BODY must be a JSON object")
        extra = parsed

    specs = [
        ("nemotron-fast", "NEMOTRON_API_KEY", "NEMOTRON_BASE_URL", "NEMOTRON_FAST_MODEL", extra),
        ("nemotron-reasoning", "NEMOTRON_API_KEY", "NEMOTRON_BASE_URL", "NEMOTRON_REASONING_MODEL", extra),
        ("ilmu", "ILMU_API_KEY", "ILMU_BASE_URL", "ILMU_CHAT_MODEL", None),
    ]
    targets: list[Target] = []
    skipped: list[str] = []
    for name, key_var, url_var, model_var, extra_body in specs:
        missing = [v for v in (key_var, url_var, model_var) if not (env.get(v) or "").strip()]
        if missing:
            skipped.append(f"{name} (missing {', '.join(missing)})")
            continue
        targets.append(Target(name, env[model_var].strip(), env[key_var].strip(), env[url_var].strip(), extra_body))
    return targets, skipped


async def _one_call(client: Any, target: Target, prompt: dict[str, str], max_tokens: int) -> Sample:
    kwargs: dict[str, Any] = {}
    if target.extra_body is not None:
        kwargs["extra_body"] = target.extra_body
    messages = [{"role": "system", "content": prompt["system"]}, {"role": "user", "content": prompt["user"]}]
    start = time.perf_counter()
    try:
        try:
            stream = await client.chat.completions.create(
                model=target.model, messages=messages, max_tokens=max_tokens, stream=True,
                stream_options={"include_usage": True}, timeout=_CALL_TIMEOUT_S, **kwargs,
            )
        except Exception as exc:  # some gateways reject stream_options with a 400
            if getattr(exc, "status_code", None) != 400:
                raise
            start = time.perf_counter()
            stream = await client.chat.completions.create(
                model=target.model, messages=messages, max_tokens=max_tokens, stream=True,
                timeout=_CALL_TIMEOUT_S, **kwargs,
            )
        return await measure_stream(stream, start=start)
    except Exception as exc:
        return Sample(error=f"{type(exc).__name__}: {str(exc)[:160]}")


async def run_target(target: Target, runs: int, max_tokens: int) -> dict[str, Any]:
    from openai import AsyncOpenAI

    per_prompt: dict[str, Any] = {}
    async with AsyncOpenAI(api_key=target.api_key, base_url=target.base_url) as client:
        for prompt in PROMPTS:
            await _one_call(client, target, prompt, max_tokens)  # warm-up: connection + cold start, discarded
            samples = [await _one_call(client, target, prompt, max_tokens) for _ in range(runs)]
            errors = sorted({s.error for s in samples if s.error})
            per_prompt[prompt["name"]] = {
                **summarise(samples),
                "error_samples": errors[:3],
                "samples": [{**asdict(sample), "tok_per_s": sample.tok_per_s} for sample in samples],
            }
    return {"model": target.model, "prompts": per_prompt}


def _fmt(value: Optional[float], digits: int = 2) -> str:
    return "-" if value is None else f"{value:.{digits}f}"


def render_markdown(results: dict[str, Any], skipped: list[str], runs: int) -> str:
    lines = [
        f"### LLM streaming latency ({runs} timed runs per prompt, 1 warm-up discarded)",
        "",
        "| target | model | prompt | ok/err | TTFT first delta p50/p95 (s) | TTFT content p50/p95 (s) | total p50/p95 (s) | tok/s p50 | tokens |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for name, res in results.items():
        for pname, s in res["prompts"].items():
            lines.append(
                f"| {name} | `{res['model']}` | {pname} | {s['ok']}/{s['errors']} "
                f"| {_fmt(s['ttft_any']['p50'])} / {_fmt(s['ttft_any']['p95'])} "
                f"| {_fmt(s['ttft_content']['p50'])} / {_fmt(s['ttft_content']['p95'])} "
                f"| {_fmt(s['total']['p50'])} / {_fmt(s['total']['p95'])} "
                f"| {_fmt(s['tok_per_s']['p50'], 1)} | {'estimated' if s['tokens_estimated'] else 'provider usage'} |"
            )
    if skipped:
        lines += ["", "Skipped: " + "; ".join(skipped)]
    lines += [
        "",
        "A thinking model emits reasoning before content, so its first-delta and content "
        "TTFT differ; the content column is what a user waits for. Small samples: read p95 as "
        "a rough ceiling, not a stable percentile.",
    ]
    return "\n".join(lines)


async def main_async(args: argparse.Namespace) -> int:
    targets, skipped = load_targets(dict(os.environ))
    if not targets:
        print("No target is fully configured.", file=sys.stderr)
        for line in skipped:
            print(f"  skipped: {line}", file=sys.stderr)
        return 2
    results: dict[str, Any] = {}
    for target in targets:
        print(f"Benchmarking {target.name} ({target.model}) ...", flush=True)
        results[target.name] = await run_target(target, args.runs, args.max_tokens)
    report = render_markdown(results, skipped, args.runs)
    print(report)
    if args.out:
        Path(args.out).write_text(json.dumps({"results": results, "skipped": skipped}, indent=2), encoding="utf-8")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--runs", type=int, default=5, help="timed runs per prompt per target (default 5)")
    parser.add_argument("--max-tokens", type=int, default=400, help="max completion tokens per call (default 400)")
    parser.add_argument("--out", default="", help="write full results as JSON to this path")
    args = parser.parse_args()
    if not 1 <= args.runs <= _MAX_RUNS:
        parser.error(f"--runs must be between 1 and {_MAX_RUNS}")
    if not 1 <= args.max_tokens <= _MAX_TOKENS_CEILING:
        parser.error(f"--max-tokens must be between 1 and {_MAX_TOKENS_CEILING}")
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
