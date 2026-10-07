-- 026_hansard_ingestion.sql
-- Resolves migration 025's deliberate deferral: 025_parliament_watch.sql
-- shipped schema + structured lookups over EMPTY tables and explicitly did
-- NOT add 'hansard' to the canonical domain list, on the grounds that
-- widening a shared surface (router_node/guard_node's _VALID_DOMAINS,
-- ingest_feed.py's copy, and the valid_domain CHECK constraint) ahead of
-- any actual ingestion would be speculative.
--
-- That ingestion pipeline now exists (scripts/ingest_parliament/), content
-- is actually being written to document_chunks with domain='hansard', and
-- CLAUDE.md's Trap #6 requires all domain-list sites to move together in
-- one PR with a migration — this is that migration. Corresponding Python
-- changes (same PR):
--   - apps/api/app/agents/router_node.py    _VALID_DOMAINS  (+ 'hansard')
--   - apps/api/scripts/ingest_feed.py       _VALID_DOMAINS  (+ 'hansard')
--   - apps/api/scripts/sources.py           domain validation surface
--     (no enum object there today beyond the shared string; nothing to
--     widen beyond the two _VALID_DOMAINS copies above — see commit body)
--
-- Ingestion pipeline safety notes (see scripts/ingest_parliament/ for the
-- implementation this migration unblocks):
--   - Every chunk written to document_chunks passes the same injection
--     scan ingest_feed.py uses (_fold_confusables + INJECTION_PATTERNS)
--     before it is embedded or inserted — no ingestion path is exempt.
--   - document_chunks dedup uses the existing content_hash UNIQUE index
--     (migration 001), not a bespoke ID scheme — re-running the pipeline
--     on an already-ingested sitting is a cheap no-op.
--   - mp_statements gets match_confidence/match_strategy (below) so a
--     statement resolved to an MP only via fuzzy name matching is visible
--     downstream instead of indistinguishable from an exact match. This
--     pipeline attributes real speech/votes to real, named politicians —
--     provenance of that attribution must not be silent.
--   - mp_votes.source_verified (already added by 025, already defaulting
--     false) is NEVER set true by the ingestion pipeline. Division-vote
--     extraction from Hansard text is the least reliable step in the
--     pipeline (a regex over an AYES/NOES text block); verification is an
--     explicit human/manual step, matching the column's existing intent.

-- ── 1. Widen document_chunks.valid_domain (016's pattern: drop + re-add) ──
ALTER TABLE document_chunks DROP CONSTRAINT IF EXISTS valid_domain;
ALTER TABLE document_chunks ADD CONSTRAINT valid_domain CHECK (
  domain IN (
    'government', 'education', 'legal', 'finance', 'healthcare',
    'epf', 'tax', 'business', 'immigration', 'culture', 'hansard'
  )
);

-- ── 2. mp_statements match-confidence tracking (additive, nullable — no ──
--       backfill needed, table ships empty against this migration) ───────
ALTER TABLE mp_statements ADD COLUMN IF NOT EXISTS match_confidence float;
ALTER TABLE mp_statements ADD COLUMN IF NOT EXISTS match_strategy varchar(32);
-- 'exact' | 'constituency_code' | 'fuzzy' | NULL (rows written before this
-- column existed, none currently since the table is empty pre-ingestion).

-- ── 3. RLS ──────────────────────────────────────────────────────────────
-- No new tables in this migration. mp_statements/mp_votes/document_chunks
-- already have RLS enabled with explicit public-read policies from
-- migrations 001 and 025 — nothing to duplicate here.
