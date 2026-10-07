-- 019_grant_programmes.sql
-- Structured grant-programme facts (amount, deadline, eligibility) to back
-- grant-finder's answers with real figures instead of an LLM "hint" guessed
-- from a RAG snippet (see app/agents/grant_finder/nodes.py's match_node,
-- which previously asked the LLM for amount_hint/deadline_hint because no
-- structured source existed).
--
-- Deliberately NOT a new column on document_chunks and NOT a foreign key
-- from it: a single grant programme's page becomes multiple RAG chunks
-- (one row per programme would either duplicate these values across every
-- chunk, or require touching the shared hybrid_search() RPC that every
-- other domain also depends on). Instead this joins to document_chunks/RAG
-- findings at query time by source_url, which both already carry — no RPC
-- change, no document_chunks migration.
--
-- Ingested via scripts/ingest/ separately from document_chunks (that
-- pipeline has no structured-field concept); rows are upserted by an
-- ingestion step keyed on source_url, same idempotency pattern as
-- document_chunks' content_hash unique index.

CREATE TABLE IF NOT EXISTS grant_programmes (
    id                      uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    source_url              text        NOT NULL,
    name                    text        NOT NULL,
    agency                  text        NOT NULL,
    grant_amount_myr        numeric,
    application_deadline    date,
    eligible_sectors        text[]      NOT NULL DEFAULT '{}',
    bumiputera_requirement  boolean,
    company_age_min_months  integer,
    created_at              timestamptz NOT NULL DEFAULT now(),
    updated_at              timestamptz NOT NULL DEFAULT now()
);

-- Stable identity key so ingestion reruns upsert rather than duplicate rows,
-- and so grant_finder can look up by source_url in one query.
CREATE UNIQUE INDEX IF NOT EXISTS grant_programmes_source_url_uq
    ON grant_programmes (source_url);
