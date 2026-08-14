"""Study Agent nodes — SPM/STPM/A-Level past-paper question extraction,
photo OCR, education RAG, and quiz-mode grading."""
from __future__ import annotations

from typing import Any

from app.agents.study_agent.state import StudyAgentState
from app.agents.tools import (
    extract_pdf_text,
    extract_questions_from_text,
    llm_complete,
    ocr_extract_text,
    query_rag_findings,
)
from app.services.llm_client import extract_json_object

# Subject → syllabus topics, scoped by education level. Extending this dict
# (rather than adding a second lookup keyed only by subject) keeps "sejarah"
# at SPM level distinct from "sejarah" at STPM level, since the syllabi and
# expected depth differ even though the subject name is the same word.
_LEVEL_SUBJECT_TOPICS: dict[str, dict[str, list[str]]] = {
    "spm": {
        "sejarah": ["kolonial", "kemerdekaan", "perlembagaan"],
        "matematik": ["algebra", "geometri", "statistik"],
        "sains": ["sel", "haba", "elektrik"],
        "bm": ["tatabahasa", "ringkasan", "novel"],
        "bi": ["grammar", "comprehension", "essay"],
    },
    "stpm": {
        "matematik_t": ["kalkulus", "algebra_linear", "kebarangkalian"],
        "ekonomi": ["mikroekonomi", "makroekonomi", "dasar_fiskal"],
        "perakaunan": ["penyata_kewangan", "jurnal", "belanjawan"],
        "sejarah": ["nasionalisme", "perang_dingin", "globalisasi"],
        "biologi": ["genetik", "ekologi", "fisiologi"],
    },
    "a-level": {
        "mathematics": ["calculus", "algebra", "statistics"],
        "physics": ["mechanics", "electricity", "waves"],
        "chemistry": ["organic", "inorganic", "physical"],
        "economics": ["microeconomics", "macroeconomics", "trade"],
        "biology": ["genetics", "ecology", "physiology"],
    },
}

_LEVEL_LABELS = {"spm": "SPM", "stpm": "STPM", "a-level": "A-Level"}


def subjects_for_level(level: str) -> list[str]:
    return list(_LEVEL_SUBJECT_TOPICS.get(level, _LEVEL_SUBJECT_TOPICS["spm"]).keys())


async def intake_node(state: StudyAgentState) -> dict[str, Any]:
    paper = state.get("paper_text") or ""
    if state.get("document_base64"):
        paper = extract_pdf_text(state["document_base64"]) or paper
    elif state.get("image_base64"):
        # Photo of a past-paper page: vision-LLM OCR (the frontend already
        # tries a client-side OCR pass first and only sends the image here
        # when that comes back empty/low-confidence, or as the primary path
        # when client-side OCR isn't available — either way this is the
        # accurate fallback/primary, not a duplicate of the same work).
        paper = await ocr_extract_text(
            state["image_base64"],
            mime_type=state.get("image_mime_type") or "image/jpeg",
            language=state.get("language") or "bm",
        ) or paper

    level = (state.get("level") or "spm").lower()
    if level not in _LEVEL_SUBJECT_TOPICS:
        level = "spm"
    valid_subjects = subjects_for_level(level)
    subject = (state.get("subject") or valid_subjects[0]).lower()
    if subject not in valid_subjects:
        subject = valid_subjects[0]

    return {
        "paper_text": paper,
        "level": level,
        "subject": subject,
        "mode": state.get("mode") or "explain",
        "turns_count": int(state.get("turns_count") or 0) + 1,
        "language": state.get("language") or "bm",
    }


async def extract_questions_node(state: StudyAgentState) -> dict[str, Any]:
    text = state.get("paper_text") or state.get("message") or ""
    questions = extract_questions_from_text(text)
    if not questions and text.strip():
        questions = [text.strip()[:500]]
    return {"questions": questions[:10]}


async def explain_node(state: StudyAgentState) -> dict[str, Any]:
    questions = state.get("questions") or []
    idx = int(state.get("active_question_index") or 0)
    if state.get("message") and questions:
        for i, q in enumerate(questions):
            if state["message"][:40].lower() in q.lower():
                idx = i
                break
    if not questions:
        return {"explanations": [], "status": "no_questions"}

    target = questions[min(idx, len(questions) - 1)]
    level_label = _LEVEL_LABELS.get(state.get("level") or "spm", "SPM")
    subject = state.get("subject") or "education"
    lang = state.get("language") or "bm"
    findings = await query_rag_findings(f"{level_label} {subject} {target}", "education", lang)
    rag_context = "\n".join(f"- {f['summary']}" for f in findings[:2])
    explanation = await llm_complete(
        f"You are a {level_label} tutor. Explain using syllabus-aligned steps and cite sources when provided.",
        f"Question: {target}\n\nSources:\n{rag_context}",
        language=lang,
    )
    explanations = list(state.get("explanations") or [])
    explanations.append({
        "question_index": idx,
        "question": target,
        "explanation": explanation or findings[0]["summary"] if findings else "Tiada penjelasan tersedia.",
        "citations": findings,
    })
    tool_calls = list(state.get("tool_calls") or [])
    tool_calls.append({"tool": "query_rag", "domain": "education", "question_index": idx})
    return {"explanations": explanations, "active_question_index": idx, "tool_calls": tool_calls, "status": "explained"}


async def generate_quiz_node(state: StudyAgentState) -> dict[str, Any]:
    """Quiz mode: turn each extracted question into a graded quiz item with
    a model answer, instead of an unprompted explanation — the student
    attempts it first (via continue -> grade_quiz_answer_node)."""
    questions = state.get("questions") or []
    if not questions:
        return {"quiz": [], "status": "no_questions"}

    level_label = _LEVEL_LABELS.get(state.get("level") or "spm", "SPM")
    subject = state.get("subject") or "education"
    lang = state.get("language") or "bm"
    quiz: list[dict[str, Any]] = []
    for idx, q in enumerate(questions[:5]):  # cap: quiz-item generation is one LLM call each
        findings = await query_rag_findings(f"{level_label} {subject} {q}", "education", lang)
        rag_context = "\n".join(f"- {f['summary']}" for f in findings[:2])
        model_answer = await llm_complete(
            f"You are setting a {level_label} {subject} quiz. Give a concise model answer "
            "(the marking-scheme answer, not a lecture) for grading a student's attempt against.",
            f"Question: {q}\n\nSources:\n{rag_context}",
            language=lang,
            max_tokens=300,
        )
        quiz.append({
            "question_index": idx,
            "question": q,
            "model_answer": model_answer,
            "citations": findings[:2],
            "student_answer": None,
            "verdict": None,
        })
    return {"quiz": quiz, "quiz_score": 0, "quiz_answered": 0, "status": "quiz_ready"}


async def grade_quiz_answer_node(state: StudyAgentState) -> dict[str, Any]:
    """Grade one quiz-item attempt supplied via `message`, against
    `active_question_index`. Deterministic bookkeeping (score/answered
    counts) stays in Python; only the correctness judgement is asked of the
    LLM, and it's asked to return structured JSON rather than free text so
    the score can't drift from what's actually rendered."""
    quiz = list(state.get("quiz") or [])
    idx = int(state.get("active_question_index") or 0)
    if not quiz or idx >= len(quiz):
        return {"status": "quiz_index_out_of_range"}

    item = dict(quiz[idx])
    student_answer = state.get("message") or ""
    lang = state.get("language") or "bm"
    raw = await llm_complete(
        "You grade one exam-quiz answer against a model answer. Respond with ONLY a JSON object: "
        '{"correct": true|false, "partial": true|false, "feedback": "one short sentence"}. '
        "partial=true only when the answer is on the right track but incomplete.",
        f"Question: {item['question']}\nModel answer: {item['model_answer']}\nStudent answer: {student_answer}",
        language=lang,
        max_tokens=200,
    )
    verdict = extract_json_object(raw) or {"correct": False, "partial": False, "feedback": ""}

    item["student_answer"] = student_answer
    item["verdict"] = verdict
    quiz[idx] = item

    score = int(state.get("quiz_score") or 0)
    if verdict.get("correct"):
        score += 1
    elif verdict.get("partial"):
        score += 0  # tracked in verdict per-item; overall score counts full marks only
    answered = int(state.get("quiz_answered") or 0) + 1

    return {"quiz": quiz, "quiz_score": score, "quiz_answered": answered, "status": "quiz_graded"}


async def track_topics_node(state: StudyAgentState) -> dict[str, Any]:
    level = state.get("level") or "spm"
    subject = state.get("subject") or subjects_for_level(level)[0]
    progress = dict(state.get("topic_progress") or {})
    topics = _LEVEL_SUBJECT_TOPICS.get(level, {}).get(subject, ["umum"])
    for q in state.get("questions") or []:
        lower = q.lower()
        for topic in topics:
            if topic.replace("_", " ") in lower or topic in lower:
                progress[topic] = progress.get(topic, 0) + 1
    if not progress:
        progress["umum"] = len(state.get("questions") or [])
    return {"topic_progress": progress, "status": state.get("status") or "completed"}
