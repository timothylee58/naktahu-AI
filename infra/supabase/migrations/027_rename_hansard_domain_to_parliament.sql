-- 027_rename_hansard_domain_to_parliament.sql
-- Renames the 'hansard' domain slug to 'parliament'.
--
-- 'hansard' was the one artefact in this whole vertical that didn't say
-- "parliament" — the tables (parliament_bills, parliament_sessions), the
-- router (routers/parliament.py), and the ingestion package
-- (scripts/ingest_parliament/) all already do. This migration makes the
-- domain enum value consistent with everything else. Table/column names
-- specific to the Hansard transcript itself (hansard_sittings,
-- hansard_statements.jsonl, the ingest_parliament/*hansard*.py filenames)
-- are untouched — "Hansard" is the correct proper noun for the
-- parliamentary record, distinct from the RAG domain classification.
--
-- Corresponding Python changes (same PR):
--   - apps/api/app/agents/router_node.py       _VALID_DOMAINS  ('hansard' -> 'parliament')
--   - apps/api/scripts/ingest_feed.py          _VALID_DOMAINS  ('hansard' -> 'parliament')
--   - apps/api/app/agents/synthesiser_node.py  fallback_suggestions key
--   - apps/api/scripts/ingest_parliament/upload_parliament.py  document_chunks insert
--   - apps/web/src/lib/i18n/index.tsx          new domain.parliament key (bm/en/zh),
--     following the exact pattern of domain.tax/domain.epf/etc.
--
-- No document_chunks rows exist with domain='hansard' yet (the ingestion
-- pipeline has not been run against the live parlimen.gov.my site from any
-- environment that could reach it — see PR #110's body). The defensive
-- UPDATE below is a no-op today and only matters if this migration is
-- applied after ingestion has already run once with the old domain value.

-- ── 1. Rename any already-ingested rows (safe no-op if none exist) ────────
UPDATE document_chunks SET domain = 'parliament' WHERE domain = 'hansard';

-- ── 2. Re-point the hansard_segments view at the renamed domain ───────────
-- The view name itself stays (it joins Hansard statement chunks specifically,
-- not a domain-enum artefact), but its WHERE clause must track the rename or
-- it silently returns zero rows forever.
CREATE OR REPLACE VIEW hansard_segments AS
  SELECT
    dc.id,
    dc.content,
    dc.source_title,
    dc.source_url,
    dc.clause_reference AS sitting_reference,
    dc.created_at,
    mp.id              AS mp_id,
    mp.full_name       AS mp_name,
    mp.party           AS mp_party,
    mp.constituency_code,
    mp.constituency_name
  FROM document_chunks dc
  LEFT JOIN mp_profiles mp
    ON dc.source_title ILIKE '%' || mp.full_name || '%'
  WHERE dc.domain = 'parliament';

-- ── 3. Widen document_chunks.valid_domain (016's pattern: drop + re-add) ──
ALTER TABLE document_chunks DROP CONSTRAINT IF EXISTS valid_domain;
ALTER TABLE document_chunks ADD CONSTRAINT valid_domain CHECK (
  domain IN (
    'government', 'education', 'legal', 'finance', 'healthcare',
    'epf', 'tax', 'business', 'immigration', 'culture', 'parliament'
  )
);
