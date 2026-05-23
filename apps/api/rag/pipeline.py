from __future__ import annotations

import os
from typing import Any

from langchain.chains import RetrievalQA
from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_openai import ChatOpenAI

from rag.retriever import get_retriever

SYSTEM_PROMPT = (
    "You are Naktahu, a Malaysian civic AI assistant. "
    "Answer questions about Malaysian statistics and data. "
    "Always cite your source dataset and year. "
    "If you cannot find relevant data, say so honestly. "
    "Respond in the same language the user used (Bahasa Malaysia or English).\n\n"
    "Context:\n{context}"
)


def _format_docs(docs: list[Any]) -> str:
    return "\n\n".join(doc.page_content for doc in docs)


def _build_chain():
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
        openai_api_key=os.environ["OPENAI_API_KEY"],
        streaming=False,
    )
    retriever = get_retriever(k=5)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_PROMPT),
            ("human", "{question}"),
        ]
    )
    chain = (
        {"context": retriever | _format_docs, "question": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )
    return chain, retriever


async def run_query(question: str, language: str = "en") -> dict[str, Any]:
    chain, retriever = _build_chain()

    docs = await retriever.ainvoke(question)
    sources = [
        {
            "dataset": doc.metadata.get("dataset", "DOSM"),
            "year": doc.metadata.get("year", ""),
            "url": doc.metadata.get("url", ""),
            "source_title": doc.metadata.get("source_title", doc.metadata.get("dataset", "DOSM")),
            "source_url": doc.metadata.get("url", ""),
            "ministry": doc.metadata.get("ministry", "DOSM"),
        }
        for doc in docs
    ]

    answer: str = await chain.ainvoke(question)

    confidence = min(1.0, len(docs) / 5) if docs else 0.0

    return {
        "answer": answer,
        "sources": sources,
        "confidence": confidence,
    }
