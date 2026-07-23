"""Study Agent nodes — SPM past-paper question extraction + education RAG."""
from __future__ import annotations

from typing import Any

from app.agents.study_agent.state import StudyAgentState
from app.agents.tools import extract_pdf_text, extract_questions_from_text, llm_complete, query_rag_findings

_SUBJECT_TOPICS: dict[str, list[str]] = {
    "sejarah": ["kolonial", "kemerdekaan", "perlembagaan"],
    "matematik": ["algebra", "geometri", "statistik"],
    "sains": ["sel", "haba", "elektrik"],
    "bm": ["tatabahasa", "ringkasan", "novel"],
    "bi": ["grammar", "comprehension", "essay"],
}


async def intake_node(state: StudyAgentState) -> dict[str, Any]:
    paper = state.get("paper_text") or ""
    if state.get("document_base64"):
        paper = extract_pdf_text(state["document_base64"]) or paper
    subject = (state.get("subject") or "sejarah").lower()
    return {
        "paper_text": paper,
        "subject": subject,
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
    subject = state.get("subject") or "education"
    lang = state.get("language") or "bm"
    findings = await query_rag_findings(f"SPM {subject} {target}", "education", lang)
    rag_context = "\n".join(f"- {f['summary']}" for f in findings[:2])
    explanation = await llm_complete(
        "You are an SPM tutor. Explain using syllabus-aligned steps and cite sources when provided.",
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


async def track_topics_node(state: StudyAgentState) -> dict[str, Any]:
    subject = state.get("subject") or "sejarah"
    progress = dict(state.get("topic_progress") or {})
    topics = _SUBJECT_TOPICS.get(subject, ["umum"])
    for q in state.get("questions") or []:
        lower = q.lower()
        for topic in topics:
            if topic in lower:
                progress[topic] = progress.get(topic, 0) + 1
    if not progress:
        progress["umum"] = len(state.get("questions") or [])
    return {"topic_progress": progress, "status": "completed"}
