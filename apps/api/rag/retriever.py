from __future__ import annotations

import os

from langchain_community.vectorstores import SupabaseVectorStore
from supabase import create_client

from rag.embeddings import embeddings


def get_retriever(k: int = 5):
    client = create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_KEY"],
    )
    store = SupabaseVectorStore(
        client=client,
        embedding=embeddings,
        table_name="dosm_documents",
        query_name="match_documents",
    )
    return store.as_retriever(search_kwargs={"k": k})
