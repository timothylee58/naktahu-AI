"""Study Agent: STPM/A-Level level scoping, photo OCR intake, and quiz mode."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from langgraph.checkpoint.memory import MemorySaver

from app.agents.checkpointer import reset_checkpointer_for_tests
from app.agents.study_agent.graph import build_study_agent_graph, get_study_agent_graph
from app.agents.study_agent.nodes import (
    generate_quiz_node,
    grade_quiz_answer_node,
    intake_node,
    subjects_for_level,
)


@pytest.fixture(autouse=True)
def _reset_cp():
    reset_checkpointer_for_tests()
    yield
    reset_checkpointer_for_tests()


def test_subjects_for_level_covers_all_three_levels() -> None:
    assert "matematik" in subjects_for_level("spm")
    assert "ekonomi" in subjects_for_level("stpm")
    assert "economics" in subjects_for_level("a-level")


def test_subjects_for_level_falls_back_to_spm_for_unknown_level() -> None:
    assert subjects_for_level("unknown") == subjects_for_level("spm")


@pytest.mark.asyncio
async def test_intake_node_normalises_invalid_level_and_subject() -> None:
    result = await intake_node({"level": "not-a-level", "subject": "not-a-subject", "paper_text": "Soalan 1: x"})
    assert result["level"] == "spm"
    assert result["subject"] in subjects_for_level("spm")


@pytest.mark.asyncio
async def test_intake_node_keeps_valid_stpm_subject() -> None:
    result = await intake_node({"level": "stpm", "subject": "ekonomi", "paper_text": "Soalan 1: x"})
    assert result["level"] == "stpm"
    assert result["subject"] == "ekonomi"


@pytest.mark.asyncio
async def test_intake_node_runs_ocr_when_image_present_and_no_document() -> None:
    with patch("app.agents.study_agent.nodes.ocr_extract_text", AsyncMock(return_value="Soalan 1: OCR text")) as mock_ocr:
        result = await intake_node({"image_base64": "ZmFrZQ==", "image_mime_type": "image/png", "language": "en"})
    mock_ocr.assert_awaited_once_with("ZmFrZQ==", mime_type="image/png", language="en")
    assert result["paper_text"] == "Soalan 1: OCR text"


@pytest.mark.asyncio
async def test_intake_node_prefers_document_over_image_when_both_present() -> None:
    with patch("app.agents.study_agent.nodes.extract_pdf_text", return_value="from pdf") as mock_pdf, \
         patch("app.agents.study_agent.nodes.ocr_extract_text", AsyncMock(return_value="from image")) as mock_ocr:
        result = await intake_node({"document_base64": "cGRm", "image_base64": "aW1n"})
    mock_pdf.assert_called_once()
    mock_ocr.assert_not_awaited()
    assert result["paper_text"] == "from pdf"


@pytest.mark.asyncio
async def test_intake_node_degrades_to_manual_text_when_ocr_fails() -> None:
    """Trap #4-style degrade: OCR provider failure must not crash the node,
    and must not silently discard text the student already typed."""
    with patch("app.agents.study_agent.nodes.ocr_extract_text", AsyncMock(return_value="")):
        result = await intake_node({"image_base64": "ZmFrZQ==", "paper_text": "manually typed fallback"})
    assert result["paper_text"] == "manually typed fallback"


def test_study_agent_graph_compiles_with_quiz_branch() -> None:
    g = build_study_agent_graph().compile(checkpointer=MemorySaver())
    assert g is not None


@pytest.mark.asyncio
async def test_graph_routes_to_quiz_when_mode_is_quiz() -> None:
    graph = get_study_agent_graph(checkpointer=MemorySaver())
    with patch("app.agents.study_agent.nodes.query_rag_findings", AsyncMock(return_value=[])), \
         patch("app.agents.study_agent.nodes.llm_complete", AsyncMock(return_value="model answer")):
        result = await graph.ainvoke(
            {
                "session_id": "s1",
                "user_id": "u1",
                "level": "spm",
                "subject": "matematik",
                "mode": "quiz",
                "paper_text": "Soalan 1: Selesaikan 2x + 3 = 7.",
                "turns_count": 0,
            },
            config={"configurable": {"thread_id": "s1"}},
        )
    assert result["quiz"], "quiz mode should populate quiz items, not explanations"
    assert "explanations" not in result or not result["explanations"]


@pytest.mark.asyncio
async def test_graph_routes_to_explain_by_default() -> None:
    graph = get_study_agent_graph(checkpointer=MemorySaver())
    with patch("app.agents.study_agent.nodes.query_rag_findings", AsyncMock(return_value=[])), \
         patch("app.agents.study_agent.nodes.llm_complete", AsyncMock(return_value="an explanation")):
        result = await graph.ainvoke(
            {
                "session_id": "s2",
                "user_id": "u1",
                "level": "spm",
                "subject": "matematik",
                "paper_text": "Soalan 1: Selesaikan 2x + 3 = 7.",
                "turns_count": 0,
            },
            config={"configurable": {"thread_id": "s2"}},
        )
    assert result["explanations"]
    assert not result.get("quiz")


@pytest.mark.asyncio
async def test_generate_quiz_node_caps_at_five_items() -> None:
    questions = [f"Soalan {i}: ?" for i in range(1, 9)]
    with patch("app.agents.study_agent.nodes.query_rag_findings", AsyncMock(return_value=[])), \
         patch("app.agents.study_agent.nodes.llm_complete", AsyncMock(return_value="model answer")):
        result = await generate_quiz_node({"questions": questions, "level": "spm", "subject": "matematik"})
    assert len(result["quiz"]) == 5
    assert result["quiz_score"] == 0
    assert result["quiz_answered"] == 0


@pytest.mark.asyncio
async def test_grade_quiz_answer_node_marks_correct_and_increments_score() -> None:
    quiz = [{"question_index": 0, "question": "2x+3=7", "model_answer": "x=2", "student_answer": None, "verdict": None}]
    with patch(
        "app.agents.study_agent.nodes.llm_complete",
        AsyncMock(return_value='{"correct": true, "partial": false, "feedback": "Nice work."}'),
    ):
        result = await grade_quiz_answer_node(
            {"quiz": quiz, "active_question_index": 0, "message": "x=2", "quiz_score": 0, "quiz_answered": 0}
        )
    assert result["quiz_score"] == 1
    assert result["quiz_answered"] == 1
    assert result["quiz"][0]["verdict"]["correct"] is True


@pytest.mark.asyncio
async def test_grade_quiz_answer_node_degrades_to_incorrect_on_unparsable_llm_output() -> None:
    """The grading LLM call is asked for strict JSON; if a provider ever
    returns free text instead, this must not crash or silently mark the
    attempt correct — it degrades to incorrect/no-feedback instead."""
    quiz = [{"question_index": 0, "question": "q", "model_answer": "a", "student_answer": None, "verdict": None}]
    with patch("app.agents.study_agent.nodes.llm_complete", AsyncMock(return_value="not json at all")):
        result = await grade_quiz_answer_node(
            {"quiz": quiz, "active_question_index": 0, "message": "some answer", "quiz_score": 0, "quiz_answered": 0}
        )
    assert result["quiz"][0]["verdict"]["correct"] is False
    assert result["quiz_score"] == 0
    assert result["quiz_answered"] == 1


@pytest.mark.asyncio
async def test_grade_quiz_answer_node_out_of_range_index_is_a_noop() -> None:
    result = await grade_quiz_answer_node({"quiz": [], "active_question_index": 0, "message": "x"})
    assert result == {"status": "quiz_index_out_of_range"}
