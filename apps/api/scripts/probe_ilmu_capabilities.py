#!/usr/bin/env python3
"""Probe which structured-output features the ILMU chat endpoint actually honours.

Writes nothing and touches no database. Each probe makes one small chat call
(a handful of tokens), so the whole run costs a few cents at most.

Usage (from apps/api):

    ILMU_API_KEY=... python -m scripts.probe_ilmu_capabilities
    ILMU_API_KEY=... python -m scripts.probe_ilmu_capabilities --queries 12
    ANTHROPIC_API_KEY=... python -m scripts.probe_ilmu_capabilities --claude

Env: ILMU_API_KEY, ILMU_BASE_URL, ILMU_CHAT_MODEL (all read by llm_client);
--claude also needs ANTHROPIC_API_KEY.

Verdicts per probe:
  SUPPORTED    the feature came back in the shape the API contract promises
  IGNORED      HTTP 200 but the parameter had no effect (the dangerous case:
               it looks like support until you inspect the output)
  REJECTED     the endpoint returned an error naming the parameter
  ERROR        network/auth failure; says nothing about the feature

The final section runs router_node's real prompt and schema over sample queries
and reports the rate of schema-valid output, which is what decides the mode:

    ROUTER_STRUCTURED_MODE=ilmu_schema   when the json_schema probe is SUPPORTED and valid rate is ~100%
    ROUTER_STRUCTURED_MODE=claude_tool   when ILMU cannot do it and --claude passes
    (unset)                              otherwise; the prompt-and-parse path stays in force
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable

_API_ROOT = Path(__file__).resolve().parents[1]
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

import openai  # noqa: E402

from app.agents.router_node import (  # noqa: E402
    _CLASSIFY_SCHEMA,
    _ROUTER_TOOL_NAME,
    _SYSTEM_PROMPT,
    router_claude_model,
)
from app.services.llm_client import (  # noqa: E402
    ILMU_CHAT_MODEL,
    anthropic_client,
    extract_json_object,
    ilmu_client,
)

_SAMPLE_QUERIES = [
    "Berapa kadar cukai pendapatan saya?",
    "How do I register a company with SSM?",
    "我如何更新我的MyKad地址?",
    "Is Pelita Nasi Kandar packed right now?",
    "How did the vote on RUU 355 break down?",
    "Who is the MP for Bangi?",
    "Macam mana nak mohon bantuan BUDI Madani?",
    "What is the strata title transfer process?",
    "Bagaimana nak keluarkan KWSP Akaun 2?",
    "What did parliament debate about tax reform?",
    "How do I renew my passport?",
    "Syarat permohonan PTPTN untuk pelajar diploma?",
]

_WEATHER_TOOL = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get the current weather for a city.",
        "parameters": {
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
            "additionalProperties": False,
        },
    },
}


@dataclass
class Result:
    name: str
    verdict: str
    detail: str


def _messages(prompt: str) -> list[dict[str, str]]:
    return [{"role": "user", "content": prompt}]


async def _chat(**kwargs: Any) -> Any:
    return await ilmu_client.chat.completions.create(model=ILMU_CHAT_MODEL, temperature=0, **kwargs)


async def _guard(name: str, probe: Callable[[], Awaitable[Result]]) -> Result:
    try:
        return await probe()
    except openai.BadRequestError as exc:
        return Result(name, "REJECTED", f"400: {str(exc)[:160]}")
    except openai.APIStatusError as exc:
        verdict = "REJECTED" if exc.status_code in (404, 422) else "ERROR"
        return Result(name, verdict, f"{exc.status_code}: {str(exc)[:160]}")
    except Exception as exc:  # network / auth: inconclusive, never read as "unsupported"
        return Result(name, "ERROR", f"{type(exc).__name__}: {str(exc)[:160]}")


async def probe_tools_auto() -> Result:
    resp = await _chat(
        messages=_messages("What is the weather in Kuala Lumpur right now? Use the tool."),
        tools=[_WEATHER_TOOL],
        tool_choice="auto",
        max_tokens=200,
    )
    calls = resp.choices[0].message.tool_calls or []
    if calls and calls[0].function.name == "get_weather":
        return Result("tools + tool_choice=auto", "SUPPORTED", f"args={calls[0].function.arguments[:80]}")
    return Result("tools + tool_choice=auto", "IGNORED", "200 OK but no tool_calls (model answered in text)")


async def probe_tools_forced() -> Result:
    resp = await _chat(
        messages=_messages("Say hello."),
        tools=[_WEATHER_TOOL],
        tool_choice={"type": "function", "function": {"name": "get_weather"}},
        max_tokens=200,
    )
    calls = resp.choices[0].message.tool_calls or []
    if calls and calls[0].function.name == "get_weather":
        return Result("tool_choice=forced function", "SUPPORTED", f"args={calls[0].function.arguments[:80]}")
    return Result("tool_choice=forced function", "IGNORED", "200 OK but the forced tool was not called")


async def probe_json_object() -> Result:
    resp = await _chat(
        messages=_messages("Reply with a JSON object with one key 'ok' set to true."),
        response_format={"type": "json_object"},
        max_tokens=60,
    )
    raw = resp.choices[0].message.content or ""
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return Result("response_format=json_object", "IGNORED", f"200 OK but not strict JSON: {raw[:80]!r}")
    return Result("response_format=json_object", "SUPPORTED", f"parsed={parsed}")


async def probe_json_schema() -> Result:
    # A prompt that gives the model every reason to wander: only the schema can constrain it.
    resp = await _chat(
        messages=_messages("Classify this query and explain your reasoning at length: How do I renew my passport?"),
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "router_classification", "strict": True, "schema": _CLASSIFY_SCHEMA},
        },
        max_tokens=384,
    )
    raw = resp.choices[0].message.content or ""
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return Result("response_format=json_schema (strict)", "IGNORED", f"200 OK but not strict JSON: {raw[:80]!r}")
    if not _schema_valid(parsed):
        return Result(
            "response_format=json_schema (strict)",
            "IGNORED",
            f"valid JSON but schema not enforced: {str(parsed)[:120]}",
        )
    return Result("response_format=json_schema (strict)", "SUPPORTED", f"parsed={parsed}")


def _type_ok(value: Any, spec: dict[str, Any]) -> bool:
    types = spec["type"] if isinstance(spec["type"], list) else [spec["type"]]
    checks = {
        "string": lambda v: isinstance(v, str),
        "boolean": lambda v: isinstance(v, bool),
        "null": lambda v: v is None,
    }
    if not any(checks[t](value) for t in types):
        return False
    return "enum" not in spec or value in spec["enum"]


def _schema_valid(parsed: Any) -> bool:
    """Exact conformance to _CLASSIFY_SCHEMA: required keys, no extras, types, nullability, enums.

    Hand-rolled because every field is a string/boolean/null; avoids adding a dependency.
    """
    props = _CLASSIFY_SCHEMA["properties"]
    if not isinstance(parsed, dict) or set(parsed) != set(props):
        return False
    return all(_type_ok(parsed[key], spec) for key, spec in props.items())


async def router_validity(queries: list[str]) -> list[Result]:
    """Real router prompt over sample queries, both ways, so the schema's benefit is measured, not assumed."""

    async def run(name: str, extra: dict[str, Any]) -> Result:
        async def one(query: str) -> bool:
            try:
                resp = await _chat(
                    messages=[{"role": "system", "content": _SYSTEM_PROMPT}, {"role": "user", "content": query}],
                    max_tokens=384,
                    **extra,
                )
                return _schema_valid(extract_json_object(resp.choices[0].message.content or ""))
            except Exception:
                return False

        flags = await asyncio.gather(*(one(q) for q in queries))
        ok = sum(flags)
        verdict = "SUPPORTED" if flags and ok == len(flags) else "IGNORED"
        return Result(name, verdict, f"{ok}/{len(flags)} schema-valid")

    plain = await run("router prompt, plain (current path)", {})
    schema = await run(
        "router prompt, json_schema",
        {
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "router_classification", "strict": True, "schema": _CLASSIFY_SCHEMA},
            }
        },
    )
    return [plain, schema]


async def probe_claude_tool() -> Result:
    resp = await anthropic_client.messages.create(
        model=router_claude_model(),
        max_tokens=384,
        system=_SYSTEM_PROMPT,
        tools=[{"name": _ROUTER_TOOL_NAME, "description": "Record the classification.", "input_schema": _CLASSIFY_SCHEMA}],
        tool_choice={"type": "tool", "name": _ROUTER_TOOL_NAME},
        messages=[{"role": "user", "content": "How do I renew my passport?"}],
    )
    for block in resp.content:
        if getattr(block, "type", None) == "tool_use" and isinstance(block.input, dict):
            verdict = "SUPPORTED" if _schema_valid(block.input) else "IGNORED"
            return Result(f"claude tool_use ({router_claude_model()})", verdict, f"input={block.input}")
    return Result(f"claude tool_use ({router_claude_model()})", "IGNORED", "no tool_use block returned")


def _recommend(results: list[Result]) -> str:
    by_name = {r.name: r for r in results}
    schema = by_name.get("response_format=json_schema (strict)")
    routed = by_name.get("router prompt, json_schema")
    if schema and schema.verdict == "SUPPORTED" and routed and routed.verdict == "SUPPORTED":
        return "ROUTER_STRUCTURED_MODE=ilmu_schema"
    claude = next((r for r in results if r.name.startswith("claude tool_use")), None)
    if claude and claude.verdict == "SUPPORTED":
        return "ROUTER_STRUCTURED_MODE=claude_tool  (routes classification through Anthropic: your provider-order call)"
    return "leave ROUTER_STRUCTURED_MODE unset (prompt-and-parse stays in force)"


def _positive_int(raw: str) -> int:
    value = int(raw)
    if value < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return value


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--queries",
        type=_positive_int,
        default=len(_SAMPLE_QUERIES),
        help="sample queries for the router run (at least 1)",
    )
    parser.add_argument("--claude", action="store_true", help="also probe Anthropic forced tool_use")
    args = parser.parse_args()

    print(f"ILMU base_url={ilmu_client.base_url}  model={ILMU_CHAT_MODEL}\n")
    results = [
        await _guard("tools + tool_choice=auto", probe_tools_auto),
        await _guard("tool_choice=forced function", probe_tools_forced),
        await _guard("response_format=json_object", probe_json_object),
        await _guard("response_format=json_schema (strict)", probe_json_schema),
    ]
    if results[-1].verdict == "SUPPORTED" or results[-1].verdict == "IGNORED":
        results.extend(await router_validity(_SAMPLE_QUERIES[: args.queries]))
    if args.claude:
        results.append(await _guard("claude tool_use", probe_claude_tool))

    for r in results:
        print(f"[{r.verdict:<9}] {r.name}\n            {r.detail}")
    print(f"\nRecommendation: {_recommend(results)}")
    return 0


if __name__ == "__main__":  # CLI script: print is the interface here
    sys.exit(asyncio.run(main()))
