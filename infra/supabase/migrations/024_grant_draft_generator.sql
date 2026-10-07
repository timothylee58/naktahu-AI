-- =============================================================================
-- Migration 024: Grant Draft Generator agent registration
-- Registers the grant-draft-generator agent (executive summary, use-of-funds
-- narrative, financial projection SKELETON, and required-document checklist
-- for a selected grant_database row + business profile; PDF or DOCX export).
-- No new tables: reuses grant_database (020), agent_runs/generated_documents
-- (010/012), and app_metadata-driven plan gating. Only the `agents` catalogue
-- row + its orchestration metadata are new.
-- =============================================================================

-- ── 0. Defensive guard: ensure agents-table orchestration columns exist ────
-- Migrations are pasted manually (Trap #5) and are not guaranteed to have
-- run in order on every environment; these are no-ops if 017 already ran.
ALTER TABLE agents ADD COLUMN IF NOT EXISTS version text NOT NULL DEFAULT '1.0.0';
ALTER TABLE agents ADD COLUMN IF NOT EXISTS capabilities jsonb NOT NULL DEFAULT '[]';
ALTER TABLE agents ADD COLUMN IF NOT EXISTS supported_domains jsonb NOT NULL DEFAULT '[]';
ALTER TABLE agents ADD COLUMN IF NOT EXISTS supports_multi_turn boolean NOT NULL DEFAULT false;
ALTER TABLE agents ADD COLUMN IF NOT EXISTS supports_streaming boolean NOT NULL DEFAULT false;
ALTER TABLE agents ADD COLUMN IF NOT EXISTS max_timeout_seconds real NOT NULL DEFAULT 30.0;

-- ── 1. Register grant-draft-generator ───────────────────────────────────────
-- Priced at 3 agent credits (RM15 at RM5/credit, see services/billing.py
-- CREDIT_PRICE_MYR) or unlimited on the Business plan (services/agent_registry
-- .is_credit_exempt). credit_cost/plan_required here are the source of truth
-- when Supabase is reachable; app/services/agent_registry._fallback_registry()
-- carries the identical values for degraded-mode boot.
INSERT INTO agents (
  name, description, plan_required, credit_cost,
  version, capabilities, supported_domains,
  supports_multi_turn, supports_streaming, max_timeout_seconds
) VALUES (
  'grant-draft-generator',
  'Grant application draft: executive summary, use-of-funds narrative, financial projection skeleton, and required-document checklist for a selected grant + business profile. Export as PDF or Word (.docx).',
  'free', 3,
  '1.0.0',
  '["grant_drafting", "government_knowledge", "finance_knowledge", "document_generation", "human_in_the_loop", "pdf_generation", "docx_generation"]'::jsonb,
  '["government", "finance"]'::jsonb,
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
