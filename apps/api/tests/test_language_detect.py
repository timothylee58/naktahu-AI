"""Tests for app.services.language_detect — pure functions, no mocking."""
from __future__ import annotations

import pytest

from app.services.language_detect import detect_latin_language, output_matches_language


@pytest.mark.parametrize(
    "query",
    [
        # The production query that was classified "bm" and answered in Malay.
        "What should I do if I lose my MyKad?",
        "How do I register a company with SSM?",
        "What's the SME tax rate?",
        "Does my company qualify for the SME tax rates?",
    ],
)
def test_detects_english(query: str) -> None:
    assert detect_latin_language(query) == "en"


@pytest.mark.parametrize(
    "query",
    [
        "Bagaimana nak tukar MyKad yang hilang?",
        "Berapa kadar cukai pendapatan saya?",
        "Apakah syarat untuk memohon BR1M?",
        "Macam mana nak bayar cukai tanah?",
    ],
)
def test_detects_bahasa_malaysia(query: str) -> None:
    assert detect_latin_language(query) == "bm"


@pytest.mark.parametrize(
    "query",
    [
        "",
        "MyKad",  # content words only: nothing to vote on
        "EPF withdrawal",  # a single English-looking noun phrase, no function words
        "cukai pendapatan",  # BM content words are not counted
        "Is it saya yang?",  # tied 2-2: no clear winner
    ],
)
def test_unsure_returns_none_so_the_caller_keeps_its_label(query: str) -> None:
    assert detect_latin_language(query) is None


def test_one_stray_english_word_does_not_flip_a_malay_sentence() -> None:
    # 4 BM votes vs 1 English ("in"): still Malay by the 2:1 rule.
    assert detect_latin_language("Bagaimana saya boleh apply in Malaysia untuk ini?") == "bm"


def test_even_split_is_not_decided() -> None:
    assert detect_latin_language("What is the cara untuk bayar yang ini") is None


# ── output_matches_language ──────────────────────────────────────────────

def test_chinese_target_rejects_untranslated_malay() -> None:
    malay = "Jika anda kehilangan MyKad, buat laporan polis dan mohon gantian di JPN."
    assert output_matches_language(malay, "zh") is False


def test_chinese_target_accepts_chinese_with_latin_acronyms() -> None:
    chinese = "如果您遗失了 MyKad，请先报警，然后到 JPN 办事处申请补发。"
    assert output_matches_language(chinese, "zh") is True


def test_chinese_target_ignores_urls_when_measuring() -> None:
    chinese = "详情请见 https://www.jpn.gov.my/en/mykad-replacement-process-and-fees 的说明。"
    assert output_matches_language(chinese, "zh") is True


def test_english_target_rejects_chinese_and_malay() -> None:
    assert output_matches_language("如果您遗失了身份证，请报警。", "en") is False
    assert output_matches_language("Bagaimana saya boleh mohon untuk ini dan itu?", "en") is False


def test_malay_target_rejects_english() -> None:
    assert output_matches_language("What should I do if I lose my card?", "bm") is False


def test_target_language_text_passes() -> None:
    assert output_matches_language("What should I do if I lose my card?", "en") is True
    assert output_matches_language("Bagaimana saya boleh mohon untuk ini?", "bm") is True


def test_unjudgeable_text_passes_rather_than_rejecting_a_good_translation() -> None:
    assert output_matches_language("OK", "bm") is True
    assert output_matches_language("RM10", "zh") is True
    assert output_matches_language("", "en") is True
