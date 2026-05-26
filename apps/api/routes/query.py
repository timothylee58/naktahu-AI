from __future__ import annotations

from typing import Optional

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

import importlib
import os

logger = structlog.get_logger()

router = APIRouter(prefix="/query", tags=["rag-query"])


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1)
    language: str = "en"
    session_id: Optional[str] = None


class SourceItem(BaseModel):
    dataset: str
    year: str | int
    url: Optional[str] = None
    source_title: str = ""
    source_url: str = ""
    ministry: str = "DOSM"


class QueryResponse(BaseModel):
    answer: str
    sources: list[SourceItem]
    confidence: float


@router.post("", response_model=QueryResponse)
async def query_endpoint(body: QueryRequest) -> QueryResponse:
    if not os.environ.get("OPENAI_API_KEY", "").strip():
        raise HTTPException(status_code=503, detail="RAG pipeline not configured")
    try:
        pipeline = importlib.import_module("rag.pipeline")
        result = await pipeline.run_query(question=body.question, language=body.language)
        return QueryResponse(
            answer=result["answer"],
            sources=[SourceItem(**s) for s in result["sources"]],
            confidence=result["confidence"],
        )
    except Exception as exc:
        logger.exception("rag_query_failed", error=str(exc))
        raise HTTPException(status_code=500, detail="Query processing failed") from exc
