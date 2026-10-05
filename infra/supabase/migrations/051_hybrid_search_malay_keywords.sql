-- 051_hybrid_search_malay_keywords.sql
-- Two fixes to the keyword half of hybrid_search():
--
-- 1. Malay morphology. The keyword layer uses the 'simple' config (no
--    stemming; Postgres has no Malay stemmer), so "memohon" never matched a
--    chunk saying "permohonan". The API now expands each query token into an
--    OR-group of its affixed forms (app/services/malay_morph.py) and passes it
--    as the new keyword_query argument, parsed with to_tsquery('simple', ...).
--    When keyword_query is NULL (CJK-only queries, or older callers) the
--    function falls back to plainto_tsquery(query_text) exactly as before.
--
-- 2. Score scale. ts_rank_cd() is unbounded and is NOT on cosine's 0-1 scale,
--    so 0.7 * cosine + 0.3 * rank mixed incompatible units and a long,
--    keyword-dense chunk could push "similarity" above 1. Normalisation flag
--    32 (rank / (rank + 1)) bounds the keyword score to [0, 1) before
--    weighting. similarity feeds analyst_node's confidence check, so it must
--    stay a bounded 0-1 relevance score — which is why this keeps the
--    weighted sum rather than switching to rank fusion (RRF scores are
--    ~0.03 and would collapse every confidence below the 0.6 threshold).
--
-- The old 4-argument function is dropped first: adding a defaulted argument
-- via CREATE OR REPLACE would leave two overloads, and PostgREST refuses to
-- pick between them ("could not choose the best candidate function").
-- Until this is applied, the API's call with keyword_query fails and
-- vector_store.hybrid_search retries without it (old behaviour).

DROP FUNCTION IF EXISTS hybrid_search(text, vector, text, int);

CREATE OR REPLACE FUNCTION hybrid_search(
    query_text      text,
    query_embedding vector,
    domain_filter   text    DEFAULT NULL,
    match_count     int     DEFAULT 5,
    keyword_query   text    DEFAULT NULL
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
            1 - (dc.embedding <=> query_embedding) AS cosine_sim
        FROM document_chunks dc
        WHERE domain_filter IS NULL OR dc.domain = domain_filter
    ),
    bm25_scores AS (
        SELECT
            dc.id,
            -- flag 32: rank / (rank + 1), bounded to [0, 1) like cosine
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
        combined.retrieved_at
    FROM combined
    ORDER BY combined.combined_score DESC
    LIMIT match_count;
END;
$$;
