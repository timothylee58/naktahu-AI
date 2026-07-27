-- =============================================================================
-- Migration 020: Eligibility Agent schema
-- Supersedes grant-finder (single-shot) with the Eligibility Agent
-- (multi-turn business grant-eligibility matching: intake -> RAG over grant
-- docs -> scoring/near-miss/stacking-matrix -> streamed summary).
-- This is a deliberate user-directed architecture replacement, not a bug fix.
-- =============================================================================

-- ── 0. Defensive guard: ensure agents-table orchestration columns exist ────
-- Migration 017_agent_orchestration_columns.sql adds these, but migrations
-- are pasted manually (Trap #5) and are not guaranteed to have run yet on
-- every environment. These ADD COLUMN IF NOT EXISTS statements are no-ops
-- if 017 already applied, so this migration works regardless of order.
ALTER TABLE agents ADD COLUMN IF NOT EXISTS version text NOT NULL DEFAULT '1.0.0';
ALTER TABLE agents ADD COLUMN IF NOT EXISTS capabilities jsonb NOT NULL DEFAULT '[]';
ALTER TABLE agents ADD COLUMN IF NOT EXISTS supported_domains jsonb NOT NULL DEFAULT '[]';
ALTER TABLE agents ADD COLUMN IF NOT EXISTS supports_multi_turn boolean NOT NULL DEFAULT false;
ALTER TABLE agents ADD COLUMN IF NOT EXISTS supports_streaming boolean NOT NULL DEFAULT false;
ALTER TABLE agents ADD COLUMN IF NOT EXISTS max_timeout_seconds real NOT NULL DEFAULT 30.0;

-- ── 1. Retire the grant-finder agent row, register eligibility-agent ───────
DELETE FROM agents WHERE name = 'grant-finder';

INSERT INTO agents (
  name, description, plan_required, credit_cost,
  version, capabilities, supported_domains,
  supports_multi_turn, supports_streaming, max_timeout_seconds
) VALUES (
  'eligibility-agent',
  'Multi-turn business grant-eligibility matching with scoring, near-miss detection, and stacking analysis.',
  'free', 0,
  '1.0.0',
  '["grant_matching", "government_knowledge", "finance_knowledge", "conversational_intake", "multi_turn"]'::jsonb,
  '["government", "finance", "education"]'::jsonb,
  true, true, 30.0
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

-- ── 2. Drop the superseded grant_programmes table ───────────────────────────
-- Fully replaced by grant_database (richer structured schema below) +
-- eligibility_sessions (multi-turn state). Nothing else in the codebase
-- queries grant_programmes after this PR (app/services/grant_programmes.py
-- and app/agents/grant_finder/ are deleted in the same change).
DROP TABLE IF EXISTS grant_programmes;

-- ── 3. Extend document_chunks with grant-specific columns ───────────────────
ALTER TABLE document_chunks
  ADD COLUMN IF NOT EXISTS grant_amount_min_myr    numeric,
  ADD COLUMN IF NOT EXISTS grant_amount_max_myr    numeric,
  ADD COLUMN IF NOT EXISTS application_deadline    date,
  ADD COLUMN IF NOT EXISTS eligible_sectors        text[],
  ADD COLUMN IF NOT EXISTS bumiputera_required     boolean DEFAULT false,
  ADD COLUMN IF NOT EXISTS company_age_min_months  smallint,
  ADD COLUMN IF NOT EXISTS max_annual_revenue_myr  numeric,
  ADD COLUMN IF NOT EXISTS grant_type              varchar(32),  -- matching|conditional|equity|non_dilutive|financing|reimbursement
  ADD COLUMN IF NOT EXISTS agency                  text,
  ADD COLUMN IF NOT EXISTS programme_name          text,
  ADD COLUMN IF NOT EXISTS application_url         text,
  ADD COLUMN IF NOT EXISTS processing_weeks_min    smallint,
  ADD COLUMN IF NOT EXISTS processing_weeks_max    smallint,
  ADD COLUMN IF NOT EXISTS stackable_with          text[];       -- list of compatible programme_names

-- ── 4. Structured grant_database table (one row per programme) ─────────────
-- Complements pgvector chunks with structured filter capability.
CREATE TABLE IF NOT EXISTS grant_database (
  id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  programme_name          text NOT NULL,
  agency                  text NOT NULL,
  grant_type              varchar(32) NOT NULL,
  amount_min_myr          numeric,
  amount_max_myr          numeric,
  application_deadline    date,
  deadline_is_rolling     boolean DEFAULT false,  -- some grants have no fixed deadline
  eligible_sectors        text[],
  bumiputera_required     boolean DEFAULT false,
  company_age_min_months  smallint DEFAULT 0,
  max_annual_revenue_myr  numeric,               -- NULL = no cap
  application_url         text,
  processing_weeks_min    smallint,
  processing_weeks_max    smallint,
  stackable_with          text[],                -- compatible programme names
  conflicts_with          text[],                -- incompatible programme names
  budget_year             smallint,
  is_active               boolean DEFAULT true,
  source_url              text,
  last_verified           date,
  notes_bm                text,
  notes_en                text,
  created_at              timestamptz DEFAULT now(),
  updated_at              timestamptz DEFAULT now()
);

-- Full-text search on grant database
CREATE INDEX IF NOT EXISTS idx_grant_db_fts
  ON grant_database USING gin(
    to_tsvector('english',
      coalesce(programme_name,'') || ' ' ||
      coalesce(agency,'') || ' ' ||
      coalesce(notes_en,'')
    )
  );

-- Sector array search
CREATE INDEX IF NOT EXISTS idx_grant_db_sectors
  ON grant_database USING gin(eligible_sectors);

-- Active grants only index
CREATE INDEX IF NOT EXISTS idx_grant_db_active
  ON grant_database(is_active, application_deadline)
  WHERE is_active = true;

-- ── 5. Eligibility sessions — multi-turn agent state ────────────────────────
CREATE TABLE IF NOT EXISTS eligibility_sessions (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id           uuid REFERENCES auth.users(id) ON DELETE CASCADE,
  session_id        text NOT NULL UNIQUE,
  -- Business profile captured during intake
  business_type     varchar(32),  -- sole_prop|sdn_bhd|startup|llp|cooperative
  registered_months smallint,
  sector            text,
  sub_sector        text,
  annual_revenue_myr numeric,
  is_bumiputera     boolean,
  employee_count    smallint,
  has_md_status     boolean DEFAULT false,  -- Malaysia Digital status
  existing_grants   text[],                -- grants already held
  current_turn      smallint DEFAULT 0,
  status            varchar(16) DEFAULT 'intake', -- intake|matching|reviewing|completed
  matched_grants    jsonb,                 -- final ranked result
  created_at        timestamptz DEFAULT now(),
  updated_at        timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_eligibility_sessions_user
  ON eligibility_sessions(user_id, created_at DESC);

-- ── 6. Seed grant_database with Budget 2026 programmes ──────────────────────
INSERT INTO grant_database (
  programme_name, agency, grant_type,
  amount_min_myr, amount_max_myr,
  eligible_sectors, bumiputera_required,
  company_age_min_months, deadline_is_rolling,
  application_url, processing_weeks_min, processing_weeks_max,
  budget_year, stackable_with, conflicts_with,
  source_url, last_verified, notes_en
) VALUES
(
  'CIP Spark', 'Cradle Fund', 'non_dilutive',
  50000, 150000,
  ARRAY['technology','ai','iot','fintech','edtech','healthtech'], false,
  0, false,
  'https://cradle.com.my/programmes/cip-spark',
  4, 8, 2026,
  ARRAY['SME Digitalization Grant','MATRADE MDG'],
  ARRAY['CIP Sprint'],
  'https://cradle.com.my/programmes', '2026-07-01',
  'Idea-to-prototype stage. Conditional convertible grant. 60% commercialisation, 40% product dev. Open to companies and individuals.'
),
(
  'CIP Sprint', 'Cradle Fund', 'conditional',
  300000, 600000,
  ARRAY['technology','ai','iot','fintech','edtech','healthtech'], false,
  6, false,
  'https://cradle.com.my/programmes/cip-sprint',
  6, 12, 2026,
  ARRAY['MATRADE MDG','MIDA Smart Automation'],
  ARRAY['CIP Spark'],
  'https://cradle.com.my/programmes', '2026-07-01',
  'Commercialisation stage. Up to RM600k over 18 months. Requires existing MVP and revenue traction.'
),
(
  'Malaysia Digital Acceleration Grant (MDAG)', 'MDEC', 'matching',
  100000, 500000,
  ARRAY['ai','blockchain','iot','quantum','digital','technology'], false,
  12, false,
  'https://www.mdec.my/malaysia-digital/mdag',
  8, 12, 2026,
  ARRAY['CIP Spark','CIP Sprint','SME Corp BEEP'],
  ARRAY['Digital Content Grant'],
  'https://www.mdec.my', '2026-07-01',
  'RM53M allocation Budget 2026. Targets AI, blockchain, IoT, quantum. Requires Malaysia Digital registration. Project proposal + financial projections required.'
),
(
  'SME Digitalization Grant (SDMG)', 'SME Corp / BSN', 'matching',
  2500, 5000,
  ARRAY['all'], false,
  6, true,
  'https://www.smecorp.gov.my/index.php/en/programmes/2015-12-21-08-38-55/sme-digitalisation-initiative',
  4, 8, 2026,
  ARRAY['HRD Corp Training Fund','MATRADE MDG'],
  ARRAY[]::text[],
  'https://www.smecorp.gov.my', '2026-07-01',
  '50% matching grant up to RM5,000. Covers e-commerce, cloud, ERP, digital marketing. Must use approved vendor list. Rolling applications.'
),
(
  'MSME Digital Grant MADANI', 'MDEC', 'matching',
  2500, 5000,
  ARRAY['all'], false,
  6, true,
  'https://www.mdec.my/godigital',
  2, 6, 2026,
  ARRAY['HRD Corp Training Fund'],
  ARRAY['SME Digitalization Grant'],
  'https://www.mdec.my', '2026-07-01',
  'RM150M allocation for 50,000 SMEs. e-commerce, cloud, digital tools. 6+ months operating history required. Business bank account required.'
),
(
  'MTDC Sandbox Fund 4', 'MTDC', 'conditional',
  250000, 5000000,
  ARRAY['technology','deeptech','ai','biotech','semiconductor'], false,
  12, false,
  'https://www.mtdc.com.my/products-services-listing/sandbox-fund/',
  8, 16, 2026,
  ARRAY['Cradle CIP Sprint','MRANTI Commercialisation'],
  ARRAY[]::text[],
  'https://www.mtdc.com.my', '2026-07-01',
  'Corporate co-investment model. RM250k-5M depending on scheme. R&D-based startups with IP. Requires corporate investor co-commitment.'
),
(
  'Market Development Grant (MDG)', 'MATRADE', 'reimbursement',
  10000, 300000,
  ARRAY['all'], false,
  12, true,
  'https://www.matrade.gov.my/en/malaysian-exporters/going-global/market-development-grant',
  6, 10, 2026,
  ARRAY['MDEC eTRADE 2.0','Cradle CIP Sprint'],
  ARRAY[]::text[],
  'https://www.matrade.gov.my', '2026-07-01',
  'Export promotion. International trade fairs, virtual events, digital marketing for exports. Any exporting SME. Rolling applications.'
),
(
  'TERAJU SUPERB', 'TERAJU', 'non_dilutive',
  50000, 500000,
  ARRAY['all'], true,
  0, false,
  'https://www.teraju.gov.my/superb',
  8, 16, 2026,
  ARRAY['SME Corp BEEP','MARA'],
  ARRAY[]::text[],
  'https://www.teraju.gov.my', '2026-07-01',
  'Bumiputera entrepreneurs only. Cohort-based with business challenge format. Timing depends on intake window. All sectors eligible.'
),
(
  'SME Automation & Digitalization Facility (ADF)', 'BNM', 'financing',
  50000, 3000000,
  ARRAY['manufacturing','services','agriculture','technology'], false,
  12, true,
  'https://www.bnm.gov.my/funds-for-smes',
  4, 8, 2026,
  ARRAY['MDEC MDAG','MIDA Smart Automation'],
  ARRAY[]::text[],
  'https://www.bnm.gov.my', '2026-07-01',
  'RM3.8B total facility. Financing (not grant) — repayment required. Up to 5% p.a. Through participating banks. Working capital + capex.'
),
(
  'HRD Corp Training Fund', 'HRD Corp', 'matching',
  5000, 25000,
  ARRAY['all'], false,
  0, true,
  'https://www.hrdcorp.gov.my',
  2, 4, 2026,
  ARRAY['SME Digitalization Grant','MDEC MDAG'],
  ARRAY[]::text[],
  'https://www.hrdcorp.gov.my', '2026-07-01',
  'Training fund for registered employers. RM25k max allocation, RM5k per trainee. 7:3 disbursement ratio. 80% attendance required for final 70%.'
);

-- ── 7. RLS — public-readable grant catalogue, owner-only sessions ──────────
ALTER TABLE grant_database ENABLE ROW LEVEL SECURITY;
CREATE POLICY "grant_database_public_read"
  ON grant_database FOR SELECT
  TO anon, authenticated
  USING (true);

ALTER TABLE eligibility_sessions ENABLE ROW LEVEL SECURITY;
CREATE POLICY "eligibility_sessions_owner"
  ON eligibility_sessions FOR ALL
  TO authenticated
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);
