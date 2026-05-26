-- 005_hybrid_search_expiry_cols.sql
-- Extend hybrid_search() to return expiry_aware and source_date columns
-- added in migration 004.

CREATE OR REPLACE FUNCTION hybrid_search(
    query_text      text,
    query_embedding vector,
    domain_filter   text    DEFAULT NULL,
    match_count     int     DEFAULT 5
)
RETURNS TABLE (
    id           uuid,
    content      text,
    source_title text,
    source_url   text,
    ministry     text,
    language     varchar,
    similarity   float,
    expiry_aware boolean,
    source_date  date
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
            dc.id,
            1 - (dc.embedding <=> query_embedding) AS cosine_sim
        FROM document_chunks dc
        WHERE domain_filter IS NULL OR dc.domain = domain_filter
    ),
    bm25_scores AS (
        SELECT
            dc.id,
            ts_rank_cd(
                to_tsvector('simple', dc.content),
                plainto_tsquery('simple', query_text)
            ) AS bm25_rank
        FROM document_chunks dc
        WHERE (domain_filter IS NULL OR dc.domain = domain_filter)
          AND to_tsvector('simple', dc.content) @@ plainto_tsquery('simple', query_text)
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
        combined.source_date
    FROM combined
    ORDER BY combined.combined_score DESC
    LIMIT match_count;
END;
$$;
