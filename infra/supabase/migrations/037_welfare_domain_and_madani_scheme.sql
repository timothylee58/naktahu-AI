-- 037_welfare_domain_and_madani_scheme.sql
-- Adds 'welfare' as the 13th canonical RAG domain, and a structured
-- madani_scheme table for the new WelfareEligibilityAgent's deterministic
-- matching — mirrors grant_database's shape/pattern (migration 020),
-- not document_chunks, since eligibility filtering needs structured fields
-- (income thresholds, state, dependent-type match), not free-text RAG.
--
-- Corresponding Python/frontend changes (same PR):
--   - apps/api/app/agents/router_node.py        _VALID_DOMAINS + _SYSTEM_PROMPT
--   - apps/api/scripts/ingest_feed.py            _VALID_DOMAINS
--   - apps/api/app/agents/welfare_eligibility_agent/  new agent (state/match/
--                                                 synthesiser/graph)
--   - apps/api/app/orchestration/adapters/welfare_eligibility_agent.py
--   - apps/api/services/agent_registry.py + app/orchestration/registry.py
--   - apps/web/src/lib/i18n/index.tsx            domain.welfare + new agent's
--                                                 intake-form keys
--
-- madani_scheme is DELIBERATELY EMPTY after this migration. No scheme rows
-- are seeded here — this repo's sandbox cannot reach ihsanmadani.gov.my
-- (network egress blocked, see scripts/sources.py's docstring), so there is
-- no independently-verified scheme content to seed with. The agent's
-- match_node runs against whatever real rows a human later inserts (via a
-- proper ingestion pass once the site is reachable, or manual entry from a
-- verified source) — see match_node.py's own comment for how it behaves
-- against an empty table (an honest "no schemes loaded yet" result, not a
-- fabricated one).
--
-- eligibility_rules is a structured jsonb filter, not free text, so
-- match_node can do deterministic filtering (income threshold, state
-- match, dependent-type match) before any LLM call — same
-- scoring-first-LLM-second architecture as eligibility_agent's grant
-- matching. Shape (all keys optional, absent = no constraint):
--   {
--     "max_household_income_myr": number,
--     "max_individual_income_myr": number,
--     "states": ["selangor", ...] | null,        -- null = federal/all states
--     "requires_oku": boolean,
--     "min_dependents_children": number,
--     "min_dependents_elderly": number,
--     "employment_status": ["unemployed", "b40", ...] | null,
--     "housing_ownership": ["rented", "no_fixed_housing", ...] | null
--   }

ALTER TABLE document_chunks DROP CONSTRAINT IF EXISTS valid_domain;
ALTER TABLE document_chunks ADD CONSTRAINT valid_domain CHECK (
  domain IN (
    'government', 'education', 'legal', 'finance', 'healthcare',
    'epf', 'tax', 'business', 'immigration', 'culture', 'parliament',
    'property', 'welfare'
  )
);

CREATE TABLE IF NOT EXISTS madani_scheme (
    id                      uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    scheme_name             text        NOT NULL,
    category                text        NOT NULL,   -- madani category slug: pendapatan|pendidikan|... (scripts/sources.py's registered categories)
    scope                   text        NOT NULL DEFAULT 'federal',  -- 'federal' | 'state:<name>' — mirrors the state-prefix convention on the source site itself
    description             text        NOT NULL,
    implementing_agency     text        NOT NULL,
    eligibility_rules       jsonb       NOT NULL DEFAULT '{}',
    source_url              text        NOT NULL,   -- Maklumat Lanjut link — the primary-source citation
    aggregator_url          text,                   -- the ihsanmadani.gov.my listing page this was found on — two-tier citation (aggregator + primary)
    is_active               boolean     NOT NULL DEFAULT true,
    last_verified           date,
    created_at              timestamptz NOT NULL DEFAULT now(),
    updated_at              timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_madani_scheme_category ON madani_scheme(category) WHERE is_active;
CREATE INDEX IF NOT EXISTS idx_madani_scheme_scope ON madani_scheme(scope) WHERE is_active;
CREATE INDEX IF NOT EXISTS idx_madani_scheme_rules ON madani_scheme USING gin(eligibility_rules);

-- Public-readable catalogue, same as grant_database (migration 020) —
-- service-role ingestion writes bypass RLS entirely.
ALTER TABLE madani_scheme ENABLE ROW LEVEL SECURITY;
CREATE POLICY "madani_scheme_public_read"
  ON madani_scheme FOR SELECT
  TO anon, authenticated
  USING (is_active);
