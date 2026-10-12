-- 056_embedding_v2_bge_m3.sql
-- Side-by-side column + search functions for ILMU-hosted bge-m3 embeddings
-- (1024-dim), so the corpus can be re-embedded WITHOUT touching the live
-- OpenAI text-embedding-3-small vectors (1536-dim, column `embedding`).
--
-- Why a new column instead of altering `embedding`: vectors from different
-- models are not comparable even when dimensions match, so the live column
-- must keep serving queries until every row has a bge-m3 vector and retrieval
-- quality has been compared. Nothing here changes existing behaviour:
--   * `embedding` and hybrid_search() / hybrid_search_madani_schemes() are
--     left exactly as they are (052 / 038).
--   * New nullable columns `embedding_v2`, filled by
--     scripts/reembed_corpus.py (workflow: reembed-corpus.yml) and, once
--     EMBEDDING_WRITE_PROFILES includes ilmu_bge_m3, by every ingestion path.
--   * New functions hybrid_search_v2() / hybrid_search_madani_schemes_v2() are
--     identical to their originals but read `embedding_v2`. The API only calls
--     them when EMBEDDING_PROFILE=ilmu_bge_m3 (app/services/embedding_profiles.py).
--
-- Cutover (manual, reversible):
--   1. apply this file in the Supabase SQL editor
--   2. run the reembed-corpus workflow (probe -> live, then compare)
--   3. set EMBEDDING_WRITE_PROFILES=openai,ilmu_bge_m3 on Railway
--   4. after the compare looks right, set EMBEDDING_PROFILE=ilmu_bge_m3
--   Rollback = set EMBEDDING_PROFILE back to openai (rows written meanwhile
--   keep both vectors). A later migration drops `embedding` once soaked.
--
-- No vector index: hybrid_search computes cosine over the whole domain-filtered
-- set (no ORDER BY ... LIMIT on the distance), so an ANN index would not be
-- used — same as the existing ivfflat index on `embedding`.
--
-- Until this is applied the API keeps working on the default `openai` profile;
-- selecting ilmu_bge_m3 before applying it makes retrieval fail closed (the
-- RPC does not exist), which analyst_node answers with a clarification.

ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS embedding_v2 vector(1024);
ALTER TABLE madani_scheme   ADD COLUMN IF NOT EXISTS embedding_v2 vector(1024);

CREATE OR REPLACE FUNCTION hybrid_search_v2(
    query_text      text,
    query_embedding vector,
    domain_filter   text    DEFAULT NULL,
    match_count     int     DEFAULT 5,
    keyword_query   text    DEFAULT NULL
)
RETURNS TABLE (
    id              uuid,
    content         text,
    source_title    text,
    source_url      text,
    ministry        text,
    language        varchar,
    similarity      float,
    expiry_aware    boolean,
    source_date     date,
    effective_date  date,
    superseded_by   uuid,
    retrieved_at    timestamptz,
    effective_until date,
    announced_date  date
)
LANGUAGE plpgsql
AS $$
DECLARE
    cosine_weight float := 0.7;
    bm25_weight   float := 0.3;
    kw_query      tsquery;
BEGIN
    kw_query := CASE
        WHEN keyword_query IS NULL OR btrim(keyword_query) = ''
            THEN plainto_tsquery('simple', query_text)
        ELSE to_tsquery('simple', keyword_query)
    END;

    RETURN QUERY
    WITH cosine_scores AS (
        SELECT
            dc.id,
            1 - (dc.embedding_v2 <=> query_embedding) AS cosine_sim
        FROM document_chunks dc
        WHERE dc.embedding_v2 IS NOT NULL
          AND (domain_filter IS NULL OR dc.domain = domain_filter)
    ),
    bm25_scores AS (
        SELECT
            dc.id,
            ts_rank_cd(to_tsvector('simple', dc.content), kw_query, 32) AS bm25_rank
        FROM document_chunks dc
        WHERE (domain_filter IS NULL OR dc.domain = domain_filter)
          AND to_tsvector('simple', dc.content) @@ kw_query
    ),
    combined AS (
        SELECT
            dc.id,
            dc.content,
            dc.source_title,
            dc.source_url,
            dc.ministry,
            dc.language,
            dc.expiry_aware,
            dc.source_date,
            dc.effective_date,
            dc.superseded_by,
            dc.created_at AS retrieved_at,
            dc.effective_until,
            dc.announced_date,
            (cosine_weight * COALESCE(cs.cosine_sim, 0))
            + (bm25_weight * COALESCE(bs.bm25_rank, 0)) AS combined_score
        FROM document_chunks dc
        LEFT JOIN cosine_scores cs ON cs.id = dc.id
        LEFT JOIN bm25_scores   bs ON bs.id = dc.id
        WHERE domain_filter IS NULL OR dc.domain = domain_filter
    )
    SELECT
        combined.id,
        combined.content,
        combined.source_title,
        combined.source_url,
        combined.ministry,
        combined.language,
        combined.combined_score AS similarity,
        combined.expiry_aware,
        combined.source_date,
        combined.effective_date,
        combined.superseded_by,
        combined.retrieved_at,
        combined.effective_until,
        combined.announced_date
    FROM combined
    ORDER BY combined.combined_score DESC
    LIMIT match_count;
END;
$$;

CREATE OR REPLACE FUNCTION hybrid_search_madani_schemes_v2(
    query_text      text,
    query_embedding vector,
    category_filter text    DEFAULT NULL,
    scope_filter    text    DEFAULT NULL,
    match_count     int     DEFAULT 5
)
RETURNS TABLE (
    id                   uuid,
    scheme_name          text,
    category             text,
    scope                text,
    description          text,
    implementing_agency  text,
    source_url           text,
    aggregator_url       text,
    language             varchar,
    similarity           float,
    effective_date       date,
    superseded_by        uuid
)
LANGUAGE plpgsql
AS $$
DECLARE
    cosine_weight float := 0.7;
    bm25_weight   float := 0.3;
BEGIN
    RETURN QUERY
    WITH cosine_scores AS (
        SELECT
            ms.id,
            1 - (ms.embedding_v2 <=> query_embedding) AS cosine_sim
        FROM madani_scheme ms
        WHERE ms.is_active
          AND ms.embedding_v2 IS NOT NULL
          AND (category_filter IS NULL OR ms.category = category_filter)
          AND (scope_filter IS NULL OR ms.scope = scope_filter)
    ),
    bm25_scores AS (
        SELECT
            ms.id,
            ts_rank_cd(
                to_tsvector('simple', ms.scheme_name || ' ' || ms.description),
                plainto_tsquery('simple', query_text)
            ) AS bm25_rank
        FROM madani_scheme ms
        WHERE ms.is_active
          AND (category_filter IS NULL OR ms.category = category_filter)
          AND (scope_filter IS NULL OR ms.scope = scope_filter)
          AND to_tsvector('simple', ms.scheme_name || ' ' || ms.description) @@ plainto_tsquery('simple', query_text)
    ),
    combined AS (
        SELECT
            ms.id,
            ms.scheme_name,
            ms.category,
            ms.scope,
            ms.description,
            ms.implementing_agency,
            ms.source_url,
            ms.aggregator_url,
            ms.language,
            ms.effective_date,
            ms.superseded_by,
            (cosine_weight * COALESCE(cs.cosine_sim, 0))
            + (bm25_weight * COALESCE(bs.bm25_rank, 0)) AS combined_score
        FROM madani_scheme ms
        LEFT JOIN cosine_scores cs ON cs.id = ms.id
        LEFT JOIN bm25_scores   bs ON bs.id = ms.id
        WHERE ms.is_active
          AND (category_filter IS NULL OR ms.category = category_filter)
          AND (scope_filter IS NULL OR ms.scope = scope_filter)
    )
    SELECT
        combined.id,
        combined.scheme_name,
        combined.category,
        combined.scope,
        combined.description,
        combined.implementing_agency,
        combined.source_url,
        combined.aggregator_url,
        combined.language,
        combined.combined_score AS similarity,
        combined.effective_date,
        combined.superseded_by
    FROM combined
    ORDER BY combined.combined_score DESC
    LIMIT match_count;
END;
$$;
