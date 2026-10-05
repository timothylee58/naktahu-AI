-- 052_chunk_validity_window.sql
-- Give document_chunks a validity WINDOW instead of a single start date.
--
-- effective_date (migration 007) says when a rule starts. Nothing said when
-- it ends, or that a change had been announced but was not yet in force. The
-- failure this fixes: a tax rule valid until 31 Dec, and a new policy
-- announced in November that takes effect 1 Jan. Ingesting the announcement
-- with effective_date = next 1 Jan made analyst_node treat it as "never
-- stale" and its prefer-newest tie-break rank it FIRST — so the future rule
-- was stated as today's rule while the current one was still in force.
--
--   effective_until  last day the rule applies (NULL = open-ended / unknown).
--                    analyst_node drops chunks whose window has closed.
--   announced_date   when the change was announced (NULL = unknown). Lets the
--                    answer say "announced on X, effective from Y".
--
-- A chunk whose effective_date is in the future is treated by analyst_node as
-- a PENDING change: kept out of the "current rule" evidence and surfaced
-- separately so the synthesiser can state today's rule AND the upcoming one.
--
-- Both columns are nullable with no default, so every existing row keeps
-- today's behaviour. hybrid_search() is recreated to return them; the API
-- reads them with .get(), so it works before this migration is applied.
-- Requires migration 051 (5-argument hybrid_search) to be applied first.

ALTER TABLE document_chunks
    ADD COLUMN IF NOT EXISTS effective_until date,
    ADD COLUMN IF NOT EXISTS announced_date  date;

ALTER TABLE document_chunks
    DROP CONSTRAINT IF EXISTS document_chunks_validity_window_check;
ALTER TABLE document_chunks
    ADD CONSTRAINT document_chunks_validity_window_check
    CHECK (effective_until IS NULL OR effective_date IS NULL OR effective_until >= effective_date);

-- RETURNS TABLE changes shape, so the function must be dropped, not replaced.
DROP FUNCTION IF EXISTS hybrid_search(text, vector, text, int, text);

CREATE OR REPLACE FUNCTION hybrid_search(
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
            1 - (dc.embedding <=> query_embedding) AS cosine_sim
        FROM document_chunks dc
        WHERE domain_filter IS NULL OR dc.domain = domain_filter
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
