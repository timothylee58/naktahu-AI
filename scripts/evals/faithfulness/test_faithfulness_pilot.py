"""Tests for the faithfulness-judge pilot. Sync and dependency-light on purpose:
the eval-gate CI job installs only pytest and supabase (which brings httpx)."""
from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from scripts.evals.faithfulness import metrics
from scripts.evals.faithfulness.claims import split_claims
from scripts.evals.faithfulness.judge import JevDecideJudge, JudgeError, LexicalOverlapJudge, make_judge
from scripts.evals.faithfulness.pilot import load_jsonl, main, run_calibration
from scripts.evals.faithfulness.scoring import MAX_ERROR_RATE, ScoreRefused, score_samples
from scripts.evals.run_eval_gate import main as gate_main

SEED = Path(__file__).parent / "data" / "calibration_seed.jsonl"


class FakeJudge:
    """Deterministic judge: p from a lookup on the claim text (default 0.9)."""

    name = "fake"

    def __init__(self, table: dict[str, float] | None = None, fail_on: tuple[str, ...] = ()) -> None:
        self.table, self.fail_on = table or {}, fail_on

    def p_supported(self, *, context: str, claim: str) -> float:
        if any(f in claim for f in self.fail_on):
            raise JudgeError("boom")
        return self.table.get(claim, 0.9)


# ── claim splitting ──────────────────────────────────────────────────────────

def test_splits_sentences_in_english_malay_and_chinese():
    assert split_claims("The fund gives RM50,000. Applications close on 30 June!") == [
        "The fund gives RM50,000.", "Applications close on 30 June!"]
    assert len(split_claims("Permohonan ditutup pada 30 Jun. Pemohon mesti berdaftar enam bulan.")) == 2
    assert split_claims("申请于六月三十日截止。申请人必须已注册至少六个月。") == [
        "申请于六月三十日截止。", "申请人必须已注册至少六个月。"]


def test_decimals_and_malay_abbreviations_do_not_end_a_sentence():
    assert split_claims("The rate is 1.5 percent for Sdn. Bhd. companies this year.") == [
        "The rate is 1.5 percent for Sdn. Bhd. companies this year."]


def test_list_markers_and_citation_marks_are_stripped_and_fragments_dropped():
    out = split_claims("- First claim about funding limits [1]\n2. Second claim about the deadline [2]\nOK.")
    assert out == ["First claim about funding limits", "Second claim about the deadline"]


def test_claim_count_is_capped_and_empty_input_is_safe():
    assert len(split_claims(" ".join(f"Claim number {i} is here." for i in range(50)), max_claims=5)) == 5
    assert split_claims("") == [] and split_claims(None) == []  # type: ignore[arg-type]


# ── judges ───────────────────────────────────────────────────────────────────

def test_lexical_judge_scores_overlap_and_handles_chinese():
    j = LexicalOverlapJudge()
    assert j.p_supported(context="Applications close on 30 June", claim="Applications close on 30 June") == 1.0
    assert j.p_supported(context="Applications close on 30 June", claim="Quantum entanglement of photons") < 0.2
    assert j.p_supported(context="申请于六月三十日截止", claim="申请于六月三十日截止") == 1.0
    with pytest.raises(JudgeError):
        j.p_supported(context="x", claim="!!")


def _jev(handler, **kw) -> JevDecideJudge:
    return JevDecideJudge("http://jev.test/", transport=httpx.MockTransport(handler), **kw)


def test_jev_judge_sends_the_documented_decide_request_and_returns_p_true():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"], seen["body"], seen["auth"] = request.url.path, json.loads(request.content), request.headers.get("authorization")
        return httpx.Response(200, json={"options": ["false", "true"], "probabilities": [0.12, 0.88]})

    assert _jev(handler).p_supported(context="CTX TEXT", claim="CLAIM TEXT") == pytest.approx(0.88)
    assert seen["path"] == "/v1/decide" and seen["auth"] is None
    assert seen["body"]["kind"] == "noul"
    assert "CTX TEXT" in seen["body"]["state"] and "CLAIM TEXT" in seen["body"]["state"]
    assert seen["body"]["question"].startswith("Is the claim fully supported")


def test_jev_judge_reads_true_by_name_not_position_and_sends_a_key_only_when_set():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={"options": ["true", "false"], "probabilities": [0.7, 0.3]})

    assert _jev(handler, api_key="k-123").p_supported(context="c", claim="d") == pytest.approx(0.7)
    assert seen["auth"] == "Bearer k-123"


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(500, text="oops"),
        httpx.Response(200, text="not json"),
        httpx.Response(200, json={"options": ["false", "true"]}),
        httpx.Response(200, json={"options": ["a", "b"], "probabilities": [0.5, 0.5]}),
        httpx.Response(200, json={"options": ["false", "true"], "probabilities": [0.1, 1.7]}),
    ],
)
def test_jev_judge_failures_raise_judge_error_never_a_guessed_number(response):
    with pytest.raises(JudgeError):
        _jev(lambda request: response).p_supported(context="c", claim="d")


def test_jev_judge_truncates_an_oversized_context():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["state"] = json.loads(request.content)["state"]
        return httpx.Response(200, json={"options": ["false", "true"], "probabilities": [0.5, 0.5]})

    _jev(handler).p_supported(context="x" * 200_000, claim="the claim survives")
    assert len(seen["state"]) < 30_000 and seen["state"].endswith("the claim survives")


def test_make_judge_requires_jev_url_and_rejects_unknown_names(monkeypatch):
    monkeypatch.delenv("JEV_URL", raising=False)
    with pytest.raises(JudgeError, match="JEV_URL"):
        make_judge("jev")
    with pytest.raises(JudgeError):
        make_judge("gpt")
    assert make_judge("lexical").name == "lexical"


# ── metrics ──────────────────────────────────────────────────────────────────

def test_auroc_known_values():
    assert metrics.auroc([0, 0, 1, 1], [0.1, 0.2, 0.8, 0.9]) == 1.0
    assert metrics.auroc([1, 1, 0, 0], [0.1, 0.2, 0.8, 0.9]) == 0.0
    assert metrics.auroc([0, 1, 0, 1], [0.5, 0.5, 0.5, 0.5]) == 0.5
    assert metrics.auroc([1, 1, 1], [0.1, 0.5, 0.9]) is None
    assert metrics.auroc([0, 0, 1, 1], [0.1, 0.4, 0.35, 0.8]) == 0.75


def test_ece_is_zero_when_calibrated_and_large_when_overconfident():
    calibrated = metrics.ece([1] * 9 + [0], [0.9] * 10)
    overconfident = metrics.ece([1, 0, 1, 0, 1, 0, 1, 0, 1, 0], [0.99] * 10)
    assert calibrated == pytest.approx(0.0, abs=1e-9)
    assert overconfident > 0.4


def test_accuracy_threshold():
    assert metrics.accuracy([1, 0, 1, 0], [0.9, 0.2, 0.4, 0.6]) == 0.5


def _synthetic_rows(n_per_lang: int) -> list[dict]:
    return [{"language": lang, "label": i % 2} for lang in metrics.LANGUAGES for i in range(n_per_lang)]


def test_verdict_is_insufficient_data_below_30_per_language_even_for_a_perfect_judge():
    rows = _synthetic_rows(10)
    rep = metrics.calibration_report(rows, [float(r["label"]) for r in rows], judge="x")
    assert rep["verdict"] == "insufficient_data" and "need 30" in rep["reasons"][0]


def test_verdict_trustworthy_only_when_every_criterion_holds():
    rows = _synthetic_rows(40)
    perfect = [0.95 if r["label"] else 0.05 for r in rows]
    rep = metrics.calibration_report(rows, perfect, baseline_scores=[0.5] * len(rows), judge="x")
    assert rep["verdict"] == "trustworthy" and rep["reasons"] == []


def test_verdict_fails_a_judge_that_is_accurate_but_no_better_than_the_baseline():
    rows = _synthetic_rows(40)
    scores = [0.95 if r["label"] else 0.05 for r in rows]
    rep = metrics.calibration_report(rows, scores, baseline_scores=scores, judge="x")
    assert rep["verdict"] == "not_trustworthy"
    assert any("lexical baseline" in r for r in rep["reasons"])


def test_verdict_fails_a_judge_that_is_bad_in_one_language():
    rows = _synthetic_rows(40)
    scores = [(0.95 if r["label"] else 0.05) if r["language"] != "zh" else 0.5 for r in rows]
    rep = metrics.calibration_report(rows, scores, judge="x")
    assert rep["verdict"] == "not_trustworthy" and any(r.startswith("zh accuracy") for r in rep["reasons"])


# ── the bundled seed set ─────────────────────────────────────────────────────

def test_seed_set_is_balanced_trilingual_synthetic_and_discriminates_the_baseline():
    rows = load_jsonl(SEED)
    assert len({r["id"] for r in rows}) == len(rows) == 18
    assert all(r["synthetic"] is True for r in rows)
    for lang in metrics.LANGUAGES:
        labels = [r["label"] for r in rows if r["language"] == lang]
        assert len(labels) == 6 and sum(labels) == 3
    report = run_calibration(rows, LexicalOverlapJudge())
    assert report["verdict"] == "insufficient_data"  # the seed can never certify a judge
    assert report["auroc"] < 0.7, "seed is too easy: paraphrased positives should defeat word overlap"


def test_a_perfect_judge_beats_the_baseline_on_the_seed_set():
    rows = load_jsonl(SEED)
    table = {r["claim"]: 0.95 if r["label"] else 0.05 for r in rows}
    report = run_calibration(rows, FakeJudge(table))
    assert report["auroc"] == 1.0 and report["baseline_auroc"] < report["auroc"]


# ── scoring ──────────────────────────────────────────────────────────────────

def _samples() -> list[dict]:
    return [
        {"id": "a", "answer": "The fund gives RM50,000 to firms. Applications close on 30 June.", "contexts": ["ctx a"]},
        {"id": "b", "answer": "Applicants need six months of registration.", "contexts": ["ctx b1", "ctx b2"]},
    ]


def test_faithfulness_is_the_mean_of_per_sample_supported_ratios():
    judge = FakeJudge({"Applications close on 30 June.": 0.1})
    out = score_samples(_samples(), judge)
    assert out["faithfulness"] == pytest.approx((0.5 + 1.0) / 2)
    assert out["claims_judged"] == 3 and out["claim_errors"] == 0 and out["samples_scored"] == 2


def test_contexts_are_joined_and_all_passed_to_the_judge():
    seen: list[str] = []

    class Spy(FakeJudge):
        def p_supported(self, *, context: str, claim: str) -> float:
            seen.append(context)
            return 1.0

    score_samples(_samples()[1:], Spy())
    assert "ctx b1" in seen[0] and "ctx b2" in seen[0]


def test_a_few_judge_errors_are_counted_not_hidden_and_too_many_refuse_a_score():
    many = [{"answer": f"Claim number {i} is long enough to count.", "contexts": ["c"]} for i in range(20)]
    out = score_samples(many, FakeJudge(fail_on=("number 3 ",)))
    assert out["claim_errors"] == 1 and out["claims_judged"] == 19
    with pytest.raises(ScoreRefused, match="could not be judged"):
        score_samples(many, FakeJudge(fail_on=("Claim",)))
    assert MAX_ERROR_RATE == 0.10


def test_samples_with_no_claims_are_skipped_and_an_empty_run_refuses():
    out = score_samples(_samples() + [{"id": "c", "answer": "", "contexts": ["x"]}], FakeJudge())
    assert out["samples_skipped"] == 1 and out["samples_scored"] == 2
    with pytest.raises(ScoreRefused):
        score_samples([{"answer": "", "contexts": []}], FakeJudge())


# ── CLI, and the hand-off to the deploy gate ─────────────────────────────────

def test_score_output_is_read_by_the_existing_deploy_gate(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("FAITHFULNESS_SCORE", raising=False)
    samples = tmp_path / "s.jsonl"
    samples.write_text("\n".join(json.dumps(s) for s in _samples()), encoding="utf-8")
    out = tmp_path / "scores.json"
    assert main(["score", "--samples", str(samples), "--judge", "lexical", "--out", str(out)]) == 0
    assert "faithfulness" in json.loads(out.read_text(encoding="utf-8"))
    capsys.readouterr()
    # the gate's own --scores-json path picks the number up: it is no longer 'NOT MEASURED'
    assert gate_main(["--scores-json", str(out), "--no-record"]) in (0, 1)
    assert "NOT MEASURED" not in capsys.readouterr().out


def test_cli_reports_a_missing_jev_url_as_an_error_not_a_traceback(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("JEV_URL", raising=False)
    assert main(["calibrate", "--cases", str(SEED), "--judge", "jev"]) == 2
    assert "JEV_URL" in capsys.readouterr().err


def test_calibrate_cli_prints_the_verdict_and_can_fail_the_build(tmp_path, capsys):
    report = tmp_path / "r.json"
    assert main(["calibrate", "--cases", str(SEED), "--judge", "lexical", "--report", str(report)]) == 0
    assert "VERDICT: insufficient_data" in capsys.readouterr().out
    assert json.loads(report.read_text(encoding="utf-8"))["verdict"] == "insufficient_data"
    assert main(["calibrate", "--cases", str(SEED), "--judge", "lexical", "--fail-unless-trustworthy"]) == 1


# ── real vs synthetic: only human-labelled rows can certify a judge ──────────

from scripts.evals.faithfulness import build_synthetic_set  # noqa: E402
from scripts.evals.faithfulness.validate import validate_cases  # noqa: E402

SYNTHETIC = Path(__file__).parent / "data" / "calibration_synthetic.jsonl"


def _oracle(rows: list[dict]) -> list[float]:
    return [0.95 if r["label"] else 0.05 for r in rows]


def test_120_perfectly_judged_synthetic_rows_still_cannot_certify_a_judge():
    rows = load_jsonl(SYNTHETIC)
    rep = metrics.calibration_report(rows, _oracle(rows), judge="oracle")
    assert rep["verdict"] == "insufficient_data" and rep["n_real"] == 0
    assert rep["synthetic"]["floor"] == "pass"          # but it does clear the floor


def test_a_judge_that_fails_the_synthetic_floor_is_reported_as_such():
    rows = load_jsonl(SYNTHETIC)
    rep = metrics.calibration_report(rows, [0.5] * len(rows), judge="coin")
    assert rep["synthetic"]["floor"] == "fail" and rep["synthetic"]["floor_reasons"]


def test_the_floor_is_not_run_on_a_handful_of_synthetic_rows():
    rows = load_jsonl(SEED)
    assert metrics.calibration_report(rows, _oracle(rows))["synthetic"]["floor"] == "not_run"


def test_real_rows_decide_the_verdict_while_synthetic_rows_are_ignored_by_it():
    real = [{"language": lang, "label": i % 2, "labeller": "x"} for lang in metrics.LANGUAGES for i in range(40)]
    synth = [{**r, "synthetic": True} for r in load_jsonl(SYNTHETIC)]
    rows = real + synth
    scores = _oracle(real) + [0.5] * len(synth)         # great on real, useless on synthetic
    rep = metrics.calibration_report(rows, scores, judge="x")
    assert rep["verdict"] == "trustworthy" and rep["n_real"] == 120
    assert rep["synthetic"]["floor"] == "fail"           # reported separately, not mixed in


def test_the_lexical_baseline_fails_the_synthetic_floor_so_the_set_does_discriminate():
    rows = load_jsonl(SYNTHETIC)
    rep = run_calibration(rows, LexicalOverlapJudge())
    assert rep["synthetic"]["floor"] == "fail" and rep["synthetic"]["auroc"] < 0.6


def test_synthetic_file_is_the_generators_output_balanced_and_trilingual():
    rows = load_jsonl(SYNTHETIC)
    assert rows == build_synthetic_set.build(), "run: python -m scripts.evals.faithfulness.build_synthetic_set"
    assert len({r["id"] for r in rows}) == len(rows) == 120
    assert all(r["synthetic"] is True for r in rows)
    for lang in metrics.LANGUAGES:
        labels = [r["label"] for r in rows if r["language"] == lang]
        assert len(labels) == 40 and sum(labels) == 20
    assert not validate_cases(rows)[0]                  # synthetic rows pass the validator too


def test_every_perturbed_claim_changes_a_fact_that_the_context_states():
    rows = load_jsonl(SYNTHETIC)
    for r in (r for r in rows if r["label"] == 0 and True):
        assert r["claim"] not in r["context"]
    # the x10 amount in each 'n1' claim never appears in its own context
    for r in (r for r in rows if r["id"].endswith("-n1")):
        figure = next(tok for tok in r["claim"].replace("，", " ").split() if tok.startswith("RM") or tok.endswith("万令吉") or tok.isdigit())
        assert figure not in r["context"]


# ── validating a human-labelled set ──────────────────────────────────────────

def _real(lang: str, i: int, label: int, **over) -> dict:
    row = {"id": f"{lang}-{i}", "language": lang, "context": f"ctx {lang} {i}", "claim": f"claim {i}",
           "label": label, "labeller": "tester"}
    row.update(over)
    return row


def test_validate_accepts_a_wellformed_real_set_and_reports_progress():
    rows = [_real("bm", i, i % 2) for i in range(12)]
    problems, progress = validate_cases(rows)
    assert problems == [] and progress == {"bm": "12/30", "en": "0/30", "zh": "0/30"}


@pytest.mark.parametrize(
    "bad,needle",
    [
        ({"language": "fr"}, "language must be one of"),
        ({"label": 2}, "label must be the integer 0 or 1"),
        ({"label": True}, "label must be the integer 0 or 1"),    # JSON booleans are not labels
        ({"label": 1.0}, "label must be the integer 0 or 1"),
        ({"synthetic": "false"}, "synthetic must be true or false"),
        ({"claim": "x" * 3_000}, "claim longer than"),
        ({"claim": "  "}, "claim must be non-empty"),
        ({"labeller": ""}, "need a 'labeller'"),
        ({"context": "x" * 30_000}, "longer than"),
    ],
)
def test_validate_flags_each_kind_of_bad_row(bad, needle):
    row = _real("bm", 0, 1)
    row.update(bad)  # `bad` overrides exactly one field
    rows = [row]
    assert any(needle in p for p in validate_cases(rows)[0])


def test_validate_reports_a_non_object_row_instead_of_crashing():
    problems, _ = validate_cases([["not", "an", "object"], 5, _real("bm", 0, 1)])
    assert sum("must be a JSON object" in p for p in problems) == 2


def test_validate_cli_reports_unreadable_input_without_a_traceback(tmp_path, capsys):
    bad = tmp_path / "bad.jsonl"
    bad.write_text("{not json\n", encoding="utf-8")
    assert main(["validate", "--cases", str(bad)]) == 2
    assert main(["validate", "--cases", str(tmp_path / "missing.jsonl")]) == 2
    assert "cannot read" in capsys.readouterr().err


def test_validate_flags_duplicate_ids_duplicate_pairs_and_lopsided_labels():
    dup = [_real("bm", 0, 1), _real("bm", 0, 0, context="other")]
    assert any("duplicate id" in p for p in validate_cases(dup)[0])
    same = [_real("bm", 0, 1), {**_real("bm", 1, 1), "context": "ctx bm 0", "claim": "claim 0"}]
    assert any("appears twice" in p for p in validate_cases(same)[0])
    skewed = [_real("en", i, 1) for i in range(12)]
    assert any("keep it between" in p for p in validate_cases(skewed)[0])


def test_validate_cli_exit_codes(tmp_path, capsys):
    ok = tmp_path / "ok.jsonl"
    ok.write_text("\n".join(json.dumps(_real("bm", i, i % 2)) for i in range(12)), encoding="utf-8")
    assert main(["validate", "--cases", str(ok)]) == 0
    assert "not yet enough real rows" in capsys.readouterr().out
    assert main(["validate", "--cases", str(ok), "--require-complete"]) == 1
    bad = tmp_path / "bad.jsonl"
    bad.write_text(json.dumps(_real("bm", 0, 5)), encoding="utf-8")
    assert main(["validate", "--cases", str(bad)]) == 1
    assert "PROBLEM" in capsys.readouterr().out


def test_calibrate_cli_accepts_several_case_files(tmp_path, capsys):
    report = tmp_path / "r.json"
    assert main(["calibrate", "--cases", str(SEED), str(SYNTHETIC), "--judge", "lexical", "--report", str(report)]) == 0
    assert json.loads(report.read_text(encoding="utf-8"))["n"] == 138


def test_single_class_real_set_reports_auroc_as_undefined_not_none():
    rows = [{**_real(lang, i, 1)} for lang in metrics.LANGUAGES for i in range(metrics.MIN_PER_LANGUAGE)]
    rep = metrics.calibration_report(rows, [0.9] * len(rows), baseline_scores=[0.5] * len(rows), judge="t")
    assert any("undefined" in r for r in rep["reasons"]) and not any("None" in r for r in rep["reasons"])
