"""Unit tests for scripts/llm_latency_benchmark.py (no network: streams are faked)."""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Optional

import pytest

from scripts import llm_latency_benchmark as bench


def _chunk(content: str = "", reasoning: str = "", usage: Optional[int] = None, choices: bool = True) -> Any:
    delta = SimpleNamespace(content=content, reasoning_content=reasoning)
    return SimpleNamespace(
        choices=[SimpleNamespace(delta=delta)] if choices else [],
        usage=SimpleNamespace(completion_tokens=usage) if usage is not None else None,
    )


async def _stream(chunks: list[Any]) -> Any:
    for c in chunks:
        yield c


class _Clock:
    """Returns a scripted sequence, one value per call."""

    def __init__(self, *values: float) -> None:
        self._values = list(values)

    def __call__(self) -> float:
        return self._values.pop(0)


def test_percentile_interpolates_and_handles_edges() -> None:
    assert bench.percentile([], 50) is None
    assert bench.percentile([4.0], 95) == 4.0
    assert bench.percentile([1.0, 2.0, 3.0, 4.0], 50) == 2.5
    assert bench.percentile([1.0, 2.0, 3.0, 4.0, 5.0], 95) == pytest.approx(4.8)


@pytest.mark.asyncio
async def test_measure_stream_times_first_delta_content_and_total_with_usage() -> None:
    # clock calls: first delta, first content, end
    chunks = [_chunk(content="Hel"), _chunk(content="lo"), _chunk(usage=40, choices=False)]
    clock = _Clock(10.5, 10.5, 12.0)
    sample = await bench.measure_stream(_stream(chunks), start=10.0, clock=clock)
    # first delta and first content both arrive on the first chunk; the second chunk only
    # reads the clock once more for its own delta (value 10.5 reused), then the end is 12.0
    assert sample.ttft_any == pytest.approx(0.5)
    assert sample.ttft_content == pytest.approx(0.5)
    assert sample.total == pytest.approx(2.0)
    assert sample.tokens == 40 and sample.tokens_estimated is False
    assert sample.tok_per_s == pytest.approx(40 / 1.5)


@pytest.mark.asyncio
async def test_reasoning_before_content_gives_a_later_content_ttft() -> None:
    chunks = [_chunk(reasoning="thinking"), _chunk(content="Answer")]
    clock = _Clock(11.0, 14.0, 15.0)  # reasoning delta, content delta, end
    sample = await bench.measure_stream(_stream(chunks), start=10.0, clock=clock)
    assert sample.ttft_any == pytest.approx(1.0)
    assert sample.ttft_content == pytest.approx(4.0)


@pytest.mark.asyncio
async def test_usage_only_final_chunk_with_no_choices_does_not_raise() -> None:
    chunks = [_chunk(content="ok"), _chunk(usage=7, choices=False)]
    sample = await bench.measure_stream(_stream(chunks), start=0.0, clock=_Clock(0.2, 1.0))
    assert sample.error is None and sample.tokens == 7


@pytest.mark.asyncio
async def test_tokens_are_estimated_from_characters_when_no_usage_arrives() -> None:
    chunks = [_chunk(content="x" * 40)]
    sample = await bench.measure_stream(_stream(chunks), start=0.0, clock=_Clock(0.1, 1.1))
    assert sample.tokens == 10 and sample.tokens_estimated is True


def test_summarise_counts_errors_and_excludes_them_from_percentiles() -> None:
    good = bench.Sample(ttft_any=1.0, ttft_content=1.0, total=3.0, tokens=20)
    bad = bench.Sample(error="TimeoutError: slow")
    result = bench.summarise([good, bad])
    assert result["ok"] == 1 and result["errors"] == 1
    assert result["total"]["p50"] == 3.0
    assert bench.summarise([bad])["total"] == {"p50": None, "p95": None}


def test_load_targets_skips_unconfigured_and_never_includes_secrets_in_the_skip_list() -> None:
    env = {
        "NEMOTRON_API_KEY": "secret-value", "NEMOTRON_BASE_URL": "https://example.invalid/v1",
        "NEMOTRON_FAST_MODEL": "fast-id",
        "ILMU_API_KEY": "another-secret",
    }
    targets, skipped = bench.load_targets(env)
    assert [t.name for t in targets] == ["nemotron-fast"]
    joined = " ".join(skipped)
    assert "nemotron-reasoning (missing NEMOTRON_REASONING_MODEL)" in joined
    assert "ilmu (missing ILMU_BASE_URL, ILMU_CHAT_MODEL)" in joined
    assert "secret-value" not in joined and "another-secret" not in joined
    assert "secret-value" not in repr(targets[0])  # api_key is excluded from repr


def test_load_targets_passes_extra_body_to_nemotron_only_and_rejects_non_objects() -> None:
    base = {
        "NEMOTRON_API_KEY": "k", "NEMOTRON_BASE_URL": "u", "NEMOTRON_FAST_MODEL": "f",
        "NEMOTRON_REASONING_MODEL": "r", "ILMU_API_KEY": "k", "ILMU_BASE_URL": "u", "ILMU_CHAT_MODEL": "m",
    }
    targets, _ = bench.load_targets({**base, "NEMOTRON_EXTRA_BODY": '{"chat_template_kwargs": {"thinking": false}}'})
    by_name = {t.name: t for t in targets}
    assert by_name["nemotron-fast"].extra_body == {"chat_template_kwargs": {"thinking": False}}
    assert by_name["ilmu"].extra_body is None
    with pytest.raises(ValueError):
        bench.load_targets({**base, "NEMOTRON_EXTRA_BODY": "[1]"})


def test_render_markdown_labels_estimated_tokens_and_lists_skipped_targets() -> None:
    summary = bench.summarise([bench.Sample(ttft_any=0.4, ttft_content=0.4, total=2.0, tokens=30, tokens_estimated=True)])
    text = bench.render_markdown({"ilmu": {"model": "m", "prompts": {"intake-extraction": {**summary, "error_samples": []}}}},
                                 ["nemotron-fast (missing NEMOTRON_API_KEY)"], runs=5)
    assert "estimated" in text and "Skipped: nemotron-fast (missing NEMOTRON_API_KEY)" in text
