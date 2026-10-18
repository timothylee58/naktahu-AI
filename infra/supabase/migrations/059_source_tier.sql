-- 059_source_tier.sql
-- Record whether each chunk came from an OFFICIAL source or a COMMUNITY /
-- non-government one, so the UI can badge it truthfully.
--
-- Why a column and not "is the URL on .gov.my": real official bodies are not
-- all on .gov.my (SSM is ssm.com.my, MDEC is mdec.my, Cradle is cradle.com.my,
-- MRANTI is mranti.my), and the registry (scripts/sources.py) already holds
-- non-government pages (mymp.org.my, mban.com.my) that must never be shown as
-- official. The ingester now stamps source_tier from the registry's `tier`.
--
--   source_tier  'official' | 'community' | NULL (= unknown: no badge shown).
--
-- NULL is deliberate. A default of 'official' would assert something about
-- every historical row, including any ingested by ad-hoc scripts, so the
-- backfill below only labels rows whose host is known; everything else stays
-- NULL and the UI simply shows no badge for it.
--
-- The column is added to hybrid_search() and hybrid_search_v2() output (both
-- must be dropped and recreated because RETURNS TABLE changes shape). The API
-- reads it with .get(), so it keeps working before this is applied: citations
-- just carry no tier. Requires migrations 051/052 (5-arg hybrid_search) and
-- 056 (hybrid_search_v2). Wrapped in a transaction so there is no window in
-- which the RPCs are missing.

BEGIN;

ALTER TABLE document_chunks
    ADD COLUMN IF NOT EXISTS source_tier text;

ALTER TABLE document_chunks
    DROP CONSTRAINT IF EXISTS document_chunks_source_tier_check;
ALTER TABLE document_chunks
    ADD CONSTRAINT document_chunks_source_tier_check
    CHECK (source_tier IS NULL OR source_tier IN ('official', 'community'));

-- Backfill (community first, then official). Hosts mirror scripts/sources.py.
UPDATE document_chunks
SET source_tier = 'community'
WHERE source_tier IS NULL
  AND source_url ~* '^https?://([a-z0-9-]+\.)*(mymp\.org\.my|mban\.com\.my)([/:?#]|$)';

UPDATE document_chunks
SET source_tier = 'official'
WHERE source_tier IS NULL
  AND (
        source_url ~* '^https?://([a-z0-9-]+\.)*gov\.my([/:?#]|$)'
     OR source_url ~* '^https?://([a-z0-9-]+\.)*(ssm\.com\.my|mdec\.my|cradle\.com\.my|mranti\.my)([/:?#]|$)'
  );

DROP FUNCTION IF EXISTS hybrid_search(text, vector, text, int, text);
DROP FUNCTION IF EXISTS hybrid_search_v2(text, vector, text, int, text);

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
    announced_date  date,
    source_tier     text
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
            dc.source_tier,
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
        combined.announced_date,
        combined.source_tier
    FROM combined
    ORDER BY combined.combined_score DESC
    LIMIT match_count;
END;
$$;

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
    announced_date  date,
    source_tier     text
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
            dc.source_tier,
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
        combined.announced_date,
        combined.source_tier
    FROM combined
    ORDER BY combined.combined_score DESC
    LIMIT match_count;
END;
$$;

COMMIT;
