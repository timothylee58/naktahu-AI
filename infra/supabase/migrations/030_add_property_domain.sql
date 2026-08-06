-- 030_add_property_domain.sql
-- Adds 'property' as the 12th canonical RAG domain (land titles, e-Tanah,
-- strata management, tenancy) — part of a knowledge-expansion pass covering
-- Property, Business Compliance, EIS/Perkeso, retrenchment options, and
-- legal options. Property was fully greenfield before this migration: no
-- domain value, no ingested content, no agent.
--
-- Corresponding Python/frontend changes (same PR):
--   - apps/api/app/agents/router_node.py       _VALID_DOMAINS + _SYSTEM_PROMPT
--                                               + _DOMAIN_ALIASES (tanah/hartanah/
--                                               e-tanah/strata/sewa -> property,
--                                               eis/socso/perkeso -> epf)
--   - apps/api/app/agents/guard_node.py         _refusal_message prose (bm/en/zh)
--   - apps/api/scripts/ingest_feed.py           _VALID_DOMAINS
--   - apps/api/scripts/sources.py               docstring + new Source entries
--   - apps/api/README.md                        domain list (also fixes a
--                                                 pre-existing drift: it was
--                                                 already missing 'parliament')
--   - apps/web/src/lib/i18n/index.tsx           new domain.property key
--                                                 (bm/en/zh), plus backfilling
--                                                 domain.government/legal/finance/
--                                                 culture, which had never had
--                                                 i18n keys despite being valid
--                                                 domains since migration 016
--
-- No document_chunks rows exist with domain='property' yet — ingestion
-- against real sources (JKPTG, KPKT/strata guidance, etc.) is a manual
-- follow-up step once source URLs are verified live and Supabase/ILMU
-- credentials are available to run scripts/ingest_feed.py.

ALTER TABLE document_chunks DROP CONSTRAINT IF EXISTS valid_domain;
ALTER TABLE document_chunks ADD CONSTRAINT valid_domain CHECK (
  domain IN (
    'government', 'education', 'legal', 'finance', 'healthcare',
    'epf', 'tax', 'business', 'immigration', 'culture', 'parliament', 'property'
  )
);
