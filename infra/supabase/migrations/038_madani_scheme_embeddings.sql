-- 038_madani_scheme_embeddings.sql
-- Adds semantic search over madani_scheme (migration 037) via a DEDICATED
-- RPC, not by extending the shared hybrid_search() function (migrations
-- 002/005/008). That function is hardcoded to document_chunks's exact
-- column shape (source_title/ministry/language/expiry_aware/source_date)
-- and is the single retrieval path every domain's rag_node call depends
-- on — a UNION reconciling two different column shapes into it is exactly
-- the kind of change where a mistake breaks tax/EPF/education retrieval,
-- not just welfare. hybrid_search_madani_schemes() below is fully
-- isolated: zero blast radius to the existing function or any other
-- domain's retrieval.
--
-- Also does NOT extend madani_schemes as a second table — that table
-- would duplicate most of madani_scheme's columns (title/description/
-- category/scope/source_url/agency all already exist there). Same entity,
-- same table; this migration ALTERs the one that already exists rather
-- than creating a near-duplicate.
--
-- effective_date/superseded_by are added here (not in migration 037)
-- because they only matter once semantic-search results need to flow
-- through analyst_node's existing staleness/supersede checks (see
-- app/services/vector_store.py's hybrid_search_madani_schemes, which maps
-- each match into the same ChunkResult shape document_chunks rows use —
-- these two columns are exactly what analyst_node already reads from that
-- shape, so schemes get the same freshness handling for free instead of
-- a parallel implementation).
--
-- NO ivfflat index is created in this migration. madani_scheme has zero
-- rows (migration 037's own header comment — no independently-verified
-- scheme content exists yet). Building an ivfflat index against an empty
-- table produces a degenerate index: ivfflat clusters vectors present at
-- CREATE INDEX time, and an index built on nothing performs poorly until
-- rebuilt — pgvector's own documentation warns against this ordering.
-- Once real scheme rows exist with real embeddings, run as a manual
-- follow-up:
--   CREATE INDEX ON madani_scheme USING ivfflat (embedding vector_cosine_ops)
--   WITH (lists = 100);  -- tune `lists` to roughly sqrt(row_count) once real volume is known
-- A plain btree on (category, scope) is created below regardless — it's
-- useful at any row count and has none of ivfflat's "needs real data
-- first" caveat.

ALTER TABLE madani_scheme ADD COLUMN IF NOT EXISTS embedding vector(1536);
ALTER TABLE madani_scheme ADD COLUMN IF NOT EXISTS effective_date date;
ALTER TABLE madani_scheme ADD COLUMN IF NOT EXISTS superseded_by uuid REFERENCES madani_scheme(id);
ALTER TABLE madani_scheme ADD COLUMN IF NOT EXISTS language varchar(16) NOT NULL DEFAULT 'bm';

CREATE INDEX IF NOT EXISTS idx_madani_scheme_category_scope ON madani_scheme(category, scope);

-- Mirrors hybrid_search()'s cosine 0.7 / BM25 0.3 weighting (migration
-- 008) for consistency with the rest of the app's search behavior, over
-- madani_scheme's own columns instead of document_chunks's. category_filter/
-- scope_filter are separate optional params (not one combined domain_filter
-- like hybrid_search) because a caller may want to search within a
-- category across all scopes, or a specific state's schemes across every
-- category — collapsing them into one filter would force an artificial
-- choice neither hybrid_search()'s domain_filter nor this table's shape
-- actually needs.
CREATE OR REPLACE FUNCTION hybrid_search_madani_schemes(
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
            1 - (ms.embedding <=> query_embedding) AS cosine_sim
        FROM madani_scheme ms
        WHERE ms.is_active
          AND ms.embedding IS NOT NULL
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
