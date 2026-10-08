"""Tests for the Eligibility Agent's flag-gated Nemotron split."""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import scripts.nemotron_check as check
from app.agents.eligibility_agent import intake_node as intake
from app.agents.eligibility_agent import llm_split as split
from app.agents.eligibility_agent import synthesiser_node as syn


def _enable(**over: Any):
    cfg = dict(
        eligibility_use_nemotron=True,
        nemotron_api_key="k",
        nemotron_base_url="https://example.test/v1",
        nemotron_fast_model="fast-model",
        nemotron_reasoning_model="reasoning-model",
        nemotron_extra_body="",
    )
    cfg.update(over)
    return patch.multiple(split.settings, **cfg)


def _chunk(content: str | None, reasoning: str | None = None) -> SimpleNamespace:
    delta = SimpleNamespace(content=content, reasoning_content=reasoning)
    return SimpleNamespace(choices=[SimpleNamespace(delta=delta)])


class _Stream:
    def __init__(self, chunks: list[Any], fail_after: int | None = None) -> None:
        self.chunks, self.fail_after = chunks, fail_after

    def __aiter__(self):
        return self._gen()

    async def _gen(self):
        for i, c in enumerate(self.chunks):
            if self.fail_after is not None and i >= self.fail_after:
                raise RuntimeError("stream broke")
            yield c


def _fake_client(create: AsyncMock) -> MagicMock:
    client = MagicMock()
    client.chat.completions.create = create
    return client


# ── gating ───────────────────────────────────────────────────────────────────

def test_disabled_by_default_and_each_role_needs_its_own_model_id():
    with _enable(eligibility_use_nemotron=False, nemotron_api_key=""):
        assert not split.fast_enabled() and not split.reasoning_enabled()
    with _enable():
        assert split.fast_enabled() and split.reasoning_enabled()
    with _enable(nemotron_fast_model=""):
        assert not split.fast_enabled() and split.reasoning_enabled()
    with _enable(nemotron_reasoning_model=""):
        assert split.fast_enabled() and not split.reasoning_enabled()
    with _enable(nemotron_api_key=""):
        assert not split.fast_enabled() and not split.reasoning_enabled()
    with _enable(eligibility_use_nemotron=False):
        assert not split.fast_enabled() and not split.reasoning_enabled()


def test_extra_body_is_parsed_and_bad_json_is_ignored_not_fatal():
    with _enable(nemotron_extra_body='{"chat_template_kwargs": {"enable_thinking": false}}'):
        assert split._extra_body() == {"chat_template_kwargs": {"enable_thinking": False}}
    with _enable(nemotron_extra_body="{not json"):
        assert split._extra_body() is None
    with _enable(nemotron_extra_body="[1, 2]"):
        assert split._extra_body() is None


# ── reasoning text never reaches users ───────────────────────────────────────

def test_strip_think_removes_blocks_and_drops_an_unclosed_one():
    assert split.strip_think("<think>plan</think>Answer.") == "Answer."
    assert split.strip_think("A<think>x</think>B<think>y</think>C") == "ABC"
    assert split.strip_think("Visible.<think>never closed") == "Visible."
    assert split.strip_think("plain") == "plain"


@pytest.mark.parametrize(
    "chunks",
    [
        ["<think>hid", "den</think>Hel", "lo"],
        ["<", "think>secret</", "think>Hello"],
        ["Hel<th", "ink>zzz</think>lo"],
        ["<think>a</think>", "Hello"],
    ],
)
def test_streaming_stripper_handles_tags_split_across_chunks(chunks):
    s = split.ThinkStripper()
    out = "".join(s.feed(c) for c in chunks) + s.flush()
    assert out == "Hello"


def test_streaming_stripper_passes_ordinary_text_with_angle_brackets():
    s = split.ThinkStripper()
    out = "".join(s.feed(c) for c in ["RM1 < RM2 and ", "a <b> tag"]) + s.flush()
    assert out == "RM1 < RM2 and a <b> tag"


def test_an_unclosed_think_block_never_leaks_at_flush():
    s = split.ThinkStripper()
    assert s.feed("ok <think>secret plan") + s.flush() == "ok "


# ── the clients ──────────────────────────────────────────────────────────────

async def test_stream_reasoning_uses_the_reasoning_model_strips_thinking_and_ignores_reasoning_content():
    create = AsyncMock(return_value=_Stream([_chunk("<think>x</think>Hel", reasoning="SECRET"), _chunk("lo"), _chunk(None)]))
    with _enable(nemotron_extra_body='{"k": 1}'), patch.object(split, "_client", return_value=_fake_client(create)):
        out = "".join([t async for t in split.stream_reasoning("PROMPT", "SYSTEM")])
    assert out == "Hello"
    kw = create.await_args.kwargs
    assert kw["model"] == "reasoning-model" and kw["stream"] is True and kw["extra_body"] == {"k": 1}
    assert [m["role"] for m in kw["messages"]] == ["system", "user"]


async def test_stream_reasoning_raises_if_it_cannot_start_but_not_after_it_has():
    boom = AsyncMock(side_effect=RuntimeError("401"))
    with _enable(), patch.object(split, "_client", return_value=_fake_client(boom)):
        with pytest.raises(RuntimeError):
            _ = [t async for t in split.stream_reasoning("p", "s")]
    midway = AsyncMock(return_value=_Stream([_chunk("Partial "), _chunk("more")], fail_after=1))
    with _enable(), patch.object(split, "_client", return_value=_fake_client(midway)):
        assert "".join([t async for t in split.stream_reasoning("p", "s")]) == "Partial "


async def test_fast_complete_uses_the_fast_model_strips_thinking_and_never_raises():
    ok = AsyncMock(return_value=SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='<think>t</think>{"a": 1}'))]))
    with _enable(), patch.object(split, "_client", return_value=_fake_client(ok)):
        assert await split.fast_complete("s", "u") == '{"a": 1}'
    assert ok.await_args.kwargs["model"] == "fast-model"
    bad = AsyncMock(side_effect=RuntimeError("down"))
    with _enable(), patch.object(split, "_client", return_value=_fake_client(bad)):
        assert await split.fast_complete("s", "u") == ""
    with _enable(eligibility_use_nemotron=False, nemotron_api_key=""):
        assert await split.fast_complete("s", "u") == ""  # disabled -> "" without any client


# ── intake: fast model first, existing provider as fallback ──────────────────

async def test_intake_flag_off_is_exactly_the_old_path():
    with patch.object(intake, "llm_complete", new=AsyncMock(return_value='{"sector": "fnb"}')) as ilmu, \
         patch.object(split, "fast_complete", new=AsyncMock(return_value="")) as fast:
        out = await intake._extract_profile_fields("text", "en")
    assert out == {"sector": "fnb"}
    ilmu.assert_awaited_once()
    fast.assert_awaited_once()  # called, but disabled -> "" -> falls through


async def test_intake_uses_the_fast_model_and_skips_ilmu_when_it_answers():
    with patch.object(intake, "llm_complete", new=AsyncMock(return_value="{}")) as ilmu, \
         patch.object(split, "fast_complete", new=AsyncMock(return_value='{"sector": "tech"}')):
        out = await intake._extract_profile_fields("text", "en")
    assert out == {"sector": "tech"}
    ilmu.assert_not_awaited()


async def test_intake_falls_back_to_ilmu_when_the_fast_model_returns_nothing():
    with patch.object(intake, "llm_complete", new=AsyncMock(return_value='{"sector": "fnb"}')) as ilmu, \
         patch.object(split, "fast_complete", new=AsyncMock(return_value="")):
        assert await intake._extract_profile_fields("text", "en") == {"sector": "fnb"}
    ilmu.assert_awaited_once()


# ── synthesiser: provider order and the partial-answer rule ──────────────────

async def _collect(state: dict[str, Any]) -> list[dict[str, Any]]:
    return [e async for e in syn.synthesiser_node(state)]


def _stream_of(*tokens: str, fail: bool = False):
    async def gen(prompt: str, system_prompt: str):
        if fail:
            raise RuntimeError("provider down")
        for t in tokens:
            yield t
    return gen


def _text(events: list[dict[str, Any]]) -> str:
    return "".join(e["text"] for e in events if e["type"] == "token")


def _provider(events: list[dict[str, Any]]) -> str:
    return next(e for e in events if e["type"] == "metadata")["data"]["llm_provider"]


STATE = {"language": "en", "matched_grants": [], "near_miss_grants": []}


async def test_flag_off_uses_ilmu_and_never_touches_nemotron():
    nemo = MagicMock()
    with patch.object(syn, "_stream_ilmu", _stream_of("Hi ", "there")), patch.object(split, "stream_reasoning", nemo):
        events = await _collect(STATE)
    assert _text(events) == "Hi there" and _provider(events) == "ilmu"
    nemo.assert_not_called()


async def test_nemotron_first_when_enabled_and_ilmu_is_not_called():
    ilmu = MagicMock()
    with _enable(), patch.object(split, "stream_reasoning", _stream_of("From ", "Nemotron")), \
         patch.object(syn, "_stream_ilmu", ilmu):
        events = await _collect(STATE)
    assert _text(events) == "From Nemotron" and _provider(events) == "nemotron"
    ilmu.assert_not_called()


async def test_nemotron_failing_before_any_token_falls_back_to_ilmu():
    with _enable(), patch.object(split, "stream_reasoning", _stream_of(fail=True)), \
         patch.object(syn, "_stream_ilmu", _stream_of("ILMU answer")):
        events = await _collect(STATE)
    assert _text(events) == "ILMU answer" and _provider(events) == "ilmu"


async def test_the_full_chain_still_ends_at_anthropic():
    async def anthropic(prompt: str, system_prompt: str):
        yield "Claude answer"

    with _enable(), patch.object(split, "stream_reasoning", _stream_of(fail=True)), \
         patch.object(syn, "_stream_ilmu", _stream_of(fail=True)), patch.object(syn, "_stream_anthropic", anthropic):
        events = await _collect(STATE)
    assert _text(events) == "Claude answer" and _provider(events) == "anthropic"


async def test_a_nemotron_answer_cut_short_is_kept_and_never_doubled_by_a_fallback():
    async def partial(prompt: str, system_prompt: str):
        yield "Half an answer"
        raise RuntimeError("stream broke")   # the synthesiser must keep the partial answer

    ilmu = MagicMock()
    with _enable(), patch.object(split, "stream_reasoning", partial), patch.object(syn, "_stream_ilmu", ilmu):
        events = await _collect(STATE)
    assert _text(events) == "Half an answer" and _provider(events) == "nemotron"
    ilmu.assert_not_called()


async def test_grant_events_and_done_still_follow_the_nemotron_summary():
    grant = {"programme_name": "G", "verification": {"status": "confirmed"}}
    with _enable(), patch.object(split, "stream_reasoning", _stream_of("x")):
        events = await _collect({**STATE, "matched_grants": [grant]})
    kinds = [e["type"] for e in events]
    assert kinds == ["token", "grant", "metadata", "done"]
    assert events[1]["data"]["verification"] == {"status": "confirmed"}


# ── the live-check script ────────────────────────────────────────────────────

def _models(*ids: str) -> MagicMock:
    c = MagicMock()
    c.models.list.return_value = SimpleNamespace(data=[SimpleNamespace(id=i) for i in ids])
    c.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="<think>t</think>OK"))]
    )
    return c


def test_check_passes_when_every_configured_id_is_served_and_answers(capsys):
    with _enable(), patch.object(check.settings, "nemotron_api_key", "k"):
        assert check.main(_models("nvidia/a", "reasoning-model", "fast-model")) == 0
    out = capsys.readouterr().out
    assert "OK   fast" in out and "OK   reasoning" in out


def test_check_fails_on_an_id_missing_from_the_catalog_and_hints_at_casing(capsys):
    client = _models("Fast-Model", "reasoning-model")
    with _enable():
        assert check.main(client) == 1
    assert "not in the catalog" in capsys.readouterr().out
    client.chat.completions.create.assert_called_once()  # only the resolvable role was called


def test_check_with_nothing_configured_exits_2(capsys):
    with patch.multiple(check.settings, nemotron_api_key="", nemotron_fast_model="", nemotron_reasoning_model=""):
        assert check.main(MagicMock()) == 2
    assert "Nothing to check" in capsys.readouterr().out


def test_check_reports_an_unreachable_endpoint_as_an_error_not_a_traceback(capsys):
    client = MagicMock()
    client.models.list.side_effect = RuntimeError("dns")
    with _enable():
        assert check.main(client) == 1
    assert "could not list models" in capsys.readouterr().out


# ── Bugbot finding on PR #240: unusable fast-model output must fall back to ILMU ──

@pytest.mark.parametrize(
    "fast_reply",
    [
        "Sure! Here is the profile you asked for, but I could not find any fields.",  # chatter, no JSON
        '{"sector": "tech", ',                                                         # malformed JSON
        '["sector", "tech"]',                                                          # JSON, but not an object
        "{}",                                                                          # parsed, but nothing extracted
        '{"foo": 1, "sector": null}',                                                  # unknown keys / only nulls
    ],
)
async def test_intake_falls_back_to_ilmu_when_the_fast_reply_yields_no_fields(fast_reply):
    with patch.object(intake, "llm_complete", new=AsyncMock(return_value='{"sector": "fnb"}')) as ilmu, \
         patch.object(split, "fast_complete", new=AsyncMock(return_value=fast_reply)):
        assert await intake._extract_profile_fields("text", "en") == {"sector": "fnb"}
    ilmu.assert_awaited_once()


async def test_intake_keeps_the_fast_models_fields_when_they_parse():
    with patch.object(intake, "llm_complete", new=AsyncMock(return_value='{"sector": "fnb"}')) as ilmu, \
         patch.object(split, "fast_complete", new=AsyncMock(return_value='Here you go: {"sector": "tech"} done')):
        assert await intake._extract_profile_fields("text", "en") == {"sector": "tech"}
    ilmu.assert_not_awaited()


async def test_intake_returns_nothing_when_both_providers_give_nothing_usable():
    with patch.object(intake, "llm_complete", new=AsyncMock(return_value="no json here")), \
         patch.object(split, "fast_complete", new=AsyncMock(return_value="also none")):
        assert await intake._extract_profile_fields("text", "en") == {}


# ── cubic findings on PR #240 ────────────────────────────────────────────────

def test_check_fails_when_the_model_returns_no_visible_text(capsys):
    client = _models("fast-model", "reasoning-model")
    client.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="<think>only thoughts</think>"))]
    )
    with _enable():
        assert check.main(client) == 1
    assert "no visible text" in capsys.readouterr().out


async def test_a_partial_ilmu_answer_followed_by_anthropic_is_reported_as_both():
    async def ilmu_then_boom(prompt: str, system_prompt: str):
        yield "part "
        raise RuntimeError("cut off")

    async def anthropic(prompt: str, system_prompt: str):
        yield "rest"

    with patch.object(syn, "_stream_ilmu", ilmu_then_boom), patch.object(syn, "_stream_anthropic", anthropic):
        events = await _collect(STATE)
    assert _provider(events) == "ilmu+anthropic"
