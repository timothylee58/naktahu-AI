-- =============================================================================
-- Migration 022: Investor Intelligence — investor_profiles + agent registration
--
-- WHAT: adds `investor_profiles`, the saved investment thesis for a VC/angel
-- customer on the investor plan, and registers the `investor-intelligence`
-- agent row so the orchestration registry can see it.
--
-- WHY: the Investor Intelligence surface (POST /api/v1/investor/match) answers
-- three questions against the live grant catalogue — which grant programmes are
-- active in the investor's thesis sector, what startup stage those grants
-- actually target (so stage mismatches are flagged rather than hidden), and
-- which Budget 2026 co-investment mandates match the investor's criteria.
-- Re-typing a fund's thesis, stages, sectors and ticket band on every request
-- is not workable for a paying B2B user, so the profile is persisted.
--
-- PRIVACY: unlike `grant_database` (a public catalogue, public-read RLS) and
-- `grant_compatibility_rules` (public reference data), an investment thesis is
-- private commercial information — a fund's stage focus, ticket band and
-- co-investment appetite are competitively sensitive. RLS here is OWNER-ONLY,
-- modelled on `eligibility_sessions_owner` (migration 020). There is no anon
-- policy and no public read policy, deliberately.
--
-- ENTITLEMENT NOTE: the investor plan is a PARALLEL entitlement, not a rung on
-- the plan ladder (middleware/plan_gate._PLAN_RANK). It lives in the Supabase
-- JWT app_metadata (plan = 'investor', or an 'investor' entry in an
-- app_metadata.entitlements list). There is no subscriptions table and this
-- migration deliberately creates none.
--
-- Backend degrades to 503 / empty results (never a crash) until this file is
-- pasted into the Supabase SQL editor — Trap #5: migrations are files, not
-- reality, and nothing applies them automatically.
-- =============================================================================

-- ── 0. Defensive guard: ensure agents-table orchestration columns exist ────
-- Same guard migration 020 carries. Migration 017 adds these columns, but
-- migrations are pasted manually and are NOT guaranteed to have run in order
-- (this has already broken a paste in the user's Supabase). Each statement is
-- a no-op if 017 already applied.
ALTER TABLE agents ADD COLUMN IF NOT EXISTS version text NOT NULL DEFAULT '1.0.0';
ALTER TABLE agents ADD COLUMN IF NOT EXISTS capabilities jsonb NOT NULL DEFAULT '[]';
ALTER TABLE agents ADD COLUMN IF NOT EXISTS supported_domains jsonb NOT NULL DEFAULT '[]';
ALTER TABLE agents ADD COLUMN IF NOT EXISTS supports_multi_turn boolean NOT NULL DEFAULT false;
ALTER TABLE agents ADD COLUMN IF NOT EXISTS supports_streaming boolean NOT NULL DEFAULT false;
ALTER TABLE agents ADD COLUMN IF NOT EXISTS max_timeout_seconds real NOT NULL DEFAULT 30.0;

-- ── 1. investor_profiles ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS investor_profiles (
  id                     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id                uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  firm_name              text,
  thesis                 text,          -- free-text investment thesis
  stage                  text[],        -- pre_seed | seed | series_a | series_b | growth
  sectors                text[],        -- thesis sectors; matched against grant_database.eligible_sectors
  ticket_size_min_myr    numeric,
  ticket_size_max_myr    numeric,
  -- Whether the fund can/will co-invest alongside government matching
  -- programmes (MTDC Sandbox Fund 4, MDAG and the rest of the Budget 2026
  -- matching family require exactly this corporate co-commitment).
  co_investment_mandate  boolean NOT NULL DEFAULT false,
  created_at             timestamptz NOT NULL DEFAULT now(),
  updated_at             timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT investor_profiles_ticket_band_sane
    CHECK (
      ticket_size_min_myr IS NULL
      OR ticket_size_max_myr IS NULL
      OR ticket_size_min_myr <= ticket_size_max_myr
    )
);

-- One saved profile per user: POST /api/v1/investor/profile is an upsert, and
-- this constraint is what makes that upsert atomic rather than a racy
-- select-then-insert (the same reasoning as Trap #9's ON CONFLICT rule).
CREATE UNIQUE INDEX IF NOT EXISTS idx_investor_profiles_user_unique
  ON investor_profiles (user_id);

-- Owner lookup (btree). Kept alongside the unique index because the API also
-- orders by recency when listing.
CREATE INDEX IF NOT EXISTS idx_investor_profiles_user
  ON investor_profiles (user_id, updated_at DESC);

-- Array containment searches (sector/stage overlap against the catalogue).
CREATE INDEX IF NOT EXISTS idx_investor_profiles_sectors
  ON investor_profiles USING gin (sectors);
CREATE INDEX IF NOT EXISTS idx_investor_profiles_stage
  ON investor_profiles USING gin (stage);

-- ── 2. RLS — owner-only, private commercial data ───────────────────────────
ALTER TABLE investor_profiles ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "investor_profiles_owner" ON investor_profiles;
CREATE POLICY "investor_profiles_owner"
  ON investor_profiles FOR ALL
  TO authenticated
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

-- ── 3. Register the investor-intelligence agent ────────────────────────────
-- Column shape matches migrations 017 and 020. plan_required is left at 'free'
-- because access is enforced by the parallel investor ENTITLEMENT in
-- middleware/plan_gate.require_entitlement(), not by the agents-table plan
-- ladder — putting 'investor' in plan_required would imply an ordinal tier
-- that _PLAN_RANK deliberately does not contain.
INSERT INTO agents (
  name, description, plan_required, credit_cost,
  version, capabilities, supported_domains,
  supports_multi_turn, supports_streaming, max_timeout_seconds
) VALUES (
  'investor-intelligence',
  'Matches a VC/angel investment thesis against live Malaysian grant programmes: active programmes in thesis sectors, investor-stage alignment, and Budget 2026 co-investment mandates.',
  'free', 0,
  '1.0.0',
  '["grant_matching", "government_knowledge", "finance_knowledge", "multi_domain_rag", "single_shot"]'::jsonb,
  '["government", "finance", "business"]'::jsonb,
  false, false, 45.0
)
ON CONFLICT (name) DO UPDATE SET
  description = EXCLUDED.description,
  plan_required = EXCLUDED.plan_required,
  credit_cost = EXCLUDED.credit_cost,
  version = EXCLUDED.version,
  capabilities = EXCLUDED.capabilities,
  supported_domains = EXCLUDED.supported_domains,
  supports_multi_turn = EXCLUDED.supports_multi_turn,
  supports_streaming = EXCLUDED.supports_streaming,
  max_timeout_seconds = EXCLUDED.max_timeout_seconds;
