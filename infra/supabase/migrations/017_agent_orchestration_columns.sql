-- 017_agent_orchestration_columns.sql
-- Adds orchestration metadata to the agents table: versioning, capabilities,
-- supported domains, multi-turn/streaming flags, and operational limits.
-- Required by the orchestration layer (app/orchestration/registry.py) for
-- intelligent agent routing and version-aware session resumption.
--
-- Backend degrades gracefully: load_enhanced_registry() falls back to
-- hardcoded defaults if these columns are missing, so the app boots fine
-- before this migration runs.

-- Semantic version for code/state compatibility checks when resuming
-- checkpointed multi-turn sessions.
ALTER TABLE agents ADD COLUMN IF NOT EXISTS version text NOT NULL DEFAULT '1.0.0';

-- JSON array of AgentCapability enum values (e.g., ["tax_knowledge", "pdf_generation"]).
-- Used by get_best_agents_for_task() to score agent fitness.
ALTER TABLE agents ADD COLUMN IF NOT EXISTS capabilities jsonb NOT NULL DEFAULT '[]';

-- JSON array of RAG domain strings this agent can query.
-- Must be a subset of the 10 canonical domains (migration 016).
ALTER TABLE agents ADD COLUMN IF NOT EXISTS supported_domains jsonb NOT NULL DEFAULT '[]';

-- Whether the agent supports continue_session() (multi-turn conversational flows).
ALTER TABLE agents ADD COLUMN IF NOT EXISTS supports_multi_turn boolean NOT NULL DEFAULT false;

-- Whether the agent supports token-by-token SSE streaming.
ALTER TABLE agents ADD COLUMN IF NOT EXISTS supports_streaming boolean NOT NULL DEFAULT false;

-- Per-agent timeout budget in seconds. The orchestrator won't wait longer.
ALTER TABLE agents ADD COLUMN IF NOT EXISTS max_timeout_seconds real NOT NULL DEFAULT 30.0;

-- Output schema (JSON Schema) for response validation.
ALTER TABLE agents ADD COLUMN IF NOT EXISTS output_schema jsonb NOT NULL DEFAULT '{}';

-- Soft-delete / deprecation support for agent lifecycle management.
ALTER TABLE agents ADD COLUMN IF NOT EXISTS enabled boolean NOT NULL DEFAULT true;
ALTER TABLE agents ADD COLUMN IF NOT EXISTS deprecated boolean NOT NULL DEFAULT false;
ALTER TABLE agents ADD COLUMN IF NOT EXISTS successor text DEFAULT NULL;

-- Backfill existing agents with orchestration metadata.
UPDATE agents SET
    version = '1.0.0',
    capabilities = '["compliance_analysis","tax_knowledge","business_knowledge","epf_knowledge","pdf_generation","multi_domain_rag","human_in_the_loop","multi_turn"]',
    supported_domains = '["tax","business","epf"]',
    supports_multi_turn = true,
    max_timeout_seconds = 60.0
WHERE name = 'compliance-drafter';

UPDATE agents SET
    version = '1.0.0',
    capabilities = '["deadline_tracking","tax_knowledge","business_knowledge","single_shot"]',
    supported_domains = '["tax","business","epf"]',
    max_timeout_seconds = 10.0
WHERE name = 'deadline-monitor';

UPDATE agents SET
    version = '1.0.0',
    capabilities = '["study_assistance","education_knowledge","document_processing","multi_turn"]',
    supported_domains = '["education"]',
    supports_multi_turn = true
WHERE name = 'study-agent';

UPDATE agents SET
    version = '1.0.0',
    capabilities = '["immigration_knowledge","conversational_intake","multi_turn"]',
    supported_domains = '["immigration"]',
    supports_multi_turn = true
WHERE name = 'immigration-navigator';

UPDATE agents SET
    version = '1.0.0',
    capabilities = '["symptom_triage","healthcare_knowledge","conversational_intake","multi_turn"]',
    supported_domains = '["healthcare"]',
    supports_multi_turn = true,
    max_timeout_seconds = 20.0
WHERE name = 'health-triage';

UPDATE agents SET
    version = '1.0.0',
    capabilities = '["multi_domain_rag","government_knowledge","finance_knowledge","legal_knowledge","education_knowledge","single_shot"]',
    supported_domains = '["government","finance","legal","education"]',
    max_timeout_seconds = 45.0
WHERE name = 'research-synthesiser';

-- Insert grant-finder if not present (added after migration 010).
INSERT INTO agents (name, description, input_schema, plan_required, credit_cost, version, capabilities, supported_domains, max_timeout_seconds)
VALUES (
    'grant-finder',
    'Government grant matching for SMEs and students.',
    '{}',
    'free',
    0,
    '1.0.0',
    '["grant_matching","government_knowledge","finance_knowledge","single_shot"]',
    '["government","finance","education"]',
    20.0
)
ON CONFLICT (name) DO UPDATE SET
    version = EXCLUDED.version,
    capabilities = EXCLUDED.capabilities,
    supported_domains = EXCLUDED.supported_domains,
    max_timeout_seconds = EXCLUDED.max_timeout_seconds;
