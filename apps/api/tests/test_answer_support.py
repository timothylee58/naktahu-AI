"""Tests for app.agents.answer_support: the answer-side check that only ever lowers confidence.

The sample answers are the ones a live tax eval produced (ilmu_bge_m3 profile), so the cases are the
real decline and non-decline wordings the check has to tell apart.
"""
from __future__ import annotations

import pytest

from app.agents.answer_support import DECLINE_CONFIDENCE_CEILING, answer_declines, apply_support_check

_DECLINES = [
    # spouse-relief (was reported at confidence 0.81)
    "I could not find specific information in the provided context documents about the tax relief amount for a spouse with no income.",
    # record-keeping (0.70)
    "Based on the provided context documents, there is no specific information about how long a business must keep its tax records in Malaysia.",
    # rpgt
    "The provided context documents do not contain information about Real Property Gains Tax (RPGT) rates.",
    # withholding-royalty
    "The provided context does not contain any information about withholding tax on royalties paid to non-residents.",
    # out-of-corpus-singapore, straight and curly apostrophes
    "I don't have information on Singapore's corporate tax rate in the provided context.",
    "I don’t have information on Singapore’s corporate tax rate in the provided context.",
    # markdown around the phrase
    "Based on the provided context, there is **no specific information** on current stamp duty rates.",
    # Bahasa Malaysia and Chinese
    "Maklumat tentang kadar ini tidak terdapat dalam dokumen yang diberikan; tiada maklumat tersebut.",
    "我没有找到关于配偶减免的具体信息。",
]

_ANSWERS = [
    "30 April each year. The deadline for individual income tax e-Filing (Form BE) is 30 April each year.",
    "Businesses must register for SST if taxable goods sales exceed RM500,000 per year.",
    "Based on the provided context, specifically from the \"Individual Income Tax Rates\" document, the tax relief for EPF contributions is RM7,000.",
    "Kadar cukai pendapatan bagi PKS bagi Tahun Taksiran 2025 adalah 15% bagi RM150,000 pertama.",
    # A figure in the opening sentence means it is answering, whatever it says it lacks.
    "The documents do not mention penalties, but the deadline is 30 April each year.",
    # Not about the provided material, so a real answer even though it says "no specific".
    "There is no specific deadline for keeping receipts; keep them while the assessment can be reopened.",
    "",
]


@pytest.mark.parametrize("text", _DECLINES)
def test_a_decline_is_recognised(text: str) -> None:
    assert answer_declines(text)


@pytest.mark.parametrize("text", _ANSWERS)
def test_an_answer_is_not_a_decline(text: str) -> None:
    assert not answer_declines(text)


def test_a_decline_later_in_the_answer_does_not_count() -> None:
    assert not answer_declines("The corporate rate is twenty-four percent for resident companies. The documents do not mention a rebate.")


def test_a_decline_caps_confidence_below_the_bar_and_flags_clarification() -> None:
    update = apply_support_check({"confidence_score": 0.81}, _DECLINES[0])
    assert update["answer_declined"] is True and update["needs_clarification"] is True
    assert update["confidence_score"] == DECLINE_CONFIDENCE_CEILING < 0.6


def test_it_never_raises_confidence() -> None:
    assert apply_support_check({"confidence_score": 0.2}, _DECLINES[0])["confidence_score"] == 0.2
    assert apply_support_check({}, _DECLINES[0])["confidence_score"] == 0.0


def test_a_normal_answer_changes_nothing_but_the_flag() -> None:
    assert apply_support_check({"confidence_score": 0.9}, _ANSWERS[0]) == {"answer_declined": False}


def test_a_figureless_decline_drops_its_citations_but_a_decline_with_figures_keeps_them() -> None:
    assert apply_support_check({"confidence_score": 0.7}, _DECLINES[0])["citations"] == []
    with_figures = (
        "Based on the provided context, there is no specific information on current stamp duty rates. "
        "The 2027 Budget announces an exemption for homes up to RM500,000 from 1 January 2027."
    )
    update = apply_support_check({"confidence_score": 0.7}, with_figures)
    assert update["answer_declined"] is True and "citations" not in update


# The two declines the first live run on the branch missed (non-resident 0.83, Singapore 0.75): the
# model restated what the context contains and only then said it lacks the answer.
_NON_RESIDENT_Q = "What income tax rate applies to a non-resident individual in Malaysia?"
_NON_RESIDENT_A = (
    "The provided context documents detail specific withholding tax rates applicable to certain types of "
    "income paid to non-residents in Malaysia, ranging from 10% to 15%. However, the context does not "
    "contain information about the general income tax rate that applies to a non-resident individual."
)
_SINGAPORE_Q = "What is the corporate tax rate in Singapore?"
_SINGAPORE_A = (
    "The query asks about the corporate tax rate in Singapore, but all provided context documents pertain "
    "exclusively to Malaysia's tax system. There is no mention of Singapore's corporate tax rate in the context."
)


def test_a_decline_in_the_second_sentence_counts_when_it_is_about_the_question() -> None:
    assert answer_declines(_NON_RESIDENT_A, _NON_RESIDENT_Q)
    assert answer_declines(_SINGAPORE_A, _SINGAPORE_Q)


def test_the_second_sentence_rule_needs_the_question() -> None:
    assert not answer_declines(_NON_RESIDENT_A)
    assert not answer_declines(_SINGAPORE_A)


def test_blank_lines_between_paragraphs_do_not_hide_the_second_sentence() -> None:
    spaced = _NON_RESIDENT_A.replace(". However,", ".\n\nHowever,")
    assert answer_declines(spaced, _NON_RESIDENT_Q)


def test_a_side_remark_about_something_else_is_not_a_decline() -> None:
    q = "What is the corporate tax rate for SMEs under the Malaysian tax system?"
    side = "The SME rate is stated in the ruling. However, the documents do not mention a rebate for exporters."
    assert not answer_declines(side, q)
    assert not answer_declines("The rate is 24%. There is no change announced in the provided context.", q)


def test_apply_support_check_uses_the_query_from_state() -> None:
    update = apply_support_check({"confidence_score": 0.83, "query": _NON_RESIDENT_Q}, _NON_RESIDENT_A)
    assert update["answer_declined"] is True and update["confidence_score"] == DECLINE_CONFIDENCE_CEILING
    assert "citations" not in update  # the opening sentence carries figures, so its chips stay
