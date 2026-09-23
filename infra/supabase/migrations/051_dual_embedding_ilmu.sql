-- 051_dual_embedding_ilmu.sql
-- Dual embeddings on document_chunks: keep the existing OpenAI column, add an
-- ILMU column, and a matching search function. Query path is ILMU-first with
-- OpenAI as fallback (user decision, 2026-09-23).
--
-- Why two columns instead of migrating one:
--   The live corpus (`embedding`, vector(1536)) was built with OpenAI
--   text-embedding-3-small — confirmed against production: all 38 rows are
--   1536-dim. ILMU's embedding model outputs 4096-dim vectors. A 4096-dim
--   query cannot be compared against 1536-dim rows at all, so "use ILMU for
--   queries" is only possible if the corpus ALSO has ILMU vectors. Keeping
--   both columns means ILMU can serve retrieval while OpenAI stays a working
--   fallback — instead of one provider outage taking retrieval down (which
--   is exactly what happened: ILMU unreachable -> zero chunks -> every answer
--   "not confident enough").
--
-- The invariant that makes this safe (see llm_client.py): each column only
-- ever holds vectors from its own model, and each search function is only
-- ever queried with that same model. Vectors from different models are never
-- compared.
--
-- No vector index on embedding_ilmu, deliberately: pgvector's HNSW and
-- IVFFlat indexes cap out at 2000 dims (halfvec at 4000) — 4096 can't be
-- indexed. At 38 rows a sequential scan costs nothing; revisit (e.g. ILMU
-- reduced-dimension output, if it supports one) once the corpus is large.
--
-- Also, deliberately: this function does NOT depend on migration 048 being
-- applied. Production's hybrid_search() is still the pre-048 shape (verified
-- live). This function reads only document_chunks columns that exist in
-- production today, and vector_store.py maps optional fields with .get().
--
-- Backend degrades gracefully until this is applied: the ILMU path calls
-- hybrid_search_ilmu, which fails -> rag_node falls back to the OpenAI path
-- (hybrid_search), which keeps working. Nothing crashes.
--
-- After applying: run `python -m scripts.backfill_ilmu_embeddings` to embed
-- existing rows with ILMU. Until then embedding_ilmu is NULL everywhere, this
-- function returns nothing, and rag_node falls back to OpenAI automatically.

ALTER TABLE document_chunks
    ADD COLUMN IF NOT EXISTS embedding_ilmu vector(4096);

COMMENT ON COLUMN document_chunks.embedding_ilmu IS
    'ILMU embedding (4096-dim). Only ever written/queried with ILMU_EMBEDDING_MODEL. '
    'Never compare against `embedding` (OpenAI text-embedding-3-small, 1536-dim).';

CREATE OR REPLACE FUNCTION hybrid_search_ilmu(
    query_text      text,
    query_embedding vector(4096),
    domain_filter   text    DEFAULT NULL,
    match_count     int     DEFAULT 5
)
RETURNS TABLE (
    id             uuid,
    content        text,
    source_title   text,
    source_url     text,
    ministry       text,
    language       varchar,
    similarity     float,
    expiry_aware   boolean,
    source_date    date,
    effective_date date,
    superseded_by  uuid,
    retrieved_at   timestamptz
)
LANGUAGE plpgsql
-- Pinned search_path: the Supabase security advisor flags every existing
-- search function for a role-mutable search_path; don't add another.
SET search_path = public
AS $$
DECLARE
    cosine_weight float := 0.7;
    bm25_weight   float := 0.3;
BEGIN
    RETURN QUERY
    WITH eligible AS (
        -- Only rows that actually HAVE an ILMU vector. Without this, rows not
        -- yet backfilled would score cosine=0 and still surface via BM25,
        -- quietly mixing "semantically matched" and "keyword-only" results.
        SELECT dc.*
        FROM document_chunks dc
        WHERE dc.embedding_ilmu IS NOT NULL
          AND (domain_filter IS NULL OR dc.domain = domain_filter)
    ),
    cosine_scores AS (
        SELECT e.id, 1 - (e.embedding_ilmu <=> query_embedding) AS cosine_sim
        FROM eligible e
    ),
    bm25_scores AS (
        SELECT
            e.id,
            ts_rank_cd(
                to_tsvector('simple', e.content),
                plainto_tsquery('simple', query_text)
            ) AS bm25_rank
        FROM eligible e
        WHERE to_tsvector('simple', e.content) @@ plainto_tsquery('simple', query_text)
    )
    SELECT
        e.id,
        e.content,
        e.source_title,
        e.source_url,
        e.ministry,
        e.language,
        ((cosine_weight * COALESCE(cs.cosine_sim, 0))
          + (bm25_weight * COALESCE(bs.bm25_rank, 0)))::float AS similarity,
        e.expiry_aware,
        e.source_date,
        e.effective_date,
        e.superseded_by,
        e.created_at AS retrieved_at
    FROM eligible e
    LEFT JOIN cosine_scores cs ON cs.id = e.id
    LEFT JOIN bm25_scores   bs ON bs.id = e.id
    -- Positional, not `ORDER BY similarity`: inside PL/pgSQL, `similarity` is
    -- also this function's OUT parameter, so the bare name is ambiguous.
    ORDER BY 7 DESC
    LIMIT match_count;
END;
$$;
