-- 018_sme_compliance_navigator.sql
-- Registers the SME Compliance Navigator (PatuhiKu) orchestration agent.
-- No RAG/document_chunks change needed — this agent reads static, versioned
-- markdown knowledge files (app/agents/knowledge/*.md) via
-- app/agents/sme_compliance_navigator/context.py rather than hybrid_search,
-- so no new document_chunks.domain value is required (migration 016's
-- 10-domain CHECK constraint is untouched).
--
-- Backend degrades gracefully: load_enhanced_registry() falls back to the
-- hardcoded defaults in app/orchestration/registry.py if this row is
-- missing, so the app boots and the agent works fine before this runs.

INSERT INTO agents (
    name, description, input_schema, plan_required, credit_cost,
    version, capabilities, supported_domains, max_timeout_seconds
)
VALUES (
    'sme-compliance-navigator',
    'PatuhiKu — cross-references LHDN, EPF/SOCSO/EIS, and SSM compliance obligations for a specific SME.',
    '{}',
    'free',
    1,
    '1.0.0',
    '["compliance_analysis","tax_knowledge","payroll_knowledge","business_knowledge","deadline_tracking","multi_domain_rag","single_shot"]',
    '["tax","payroll","corporate"]',
    30.0
)
ON CONFLICT (name) DO UPDATE SET
    description = EXCLUDED.description,
    version = EXCLUDED.version,
    capabilities = EXCLUDED.capabilities,
    supported_domains = EXCLUDED.supported_domains,
    plan_required = EXCLUDED.plan_required,
    credit_cost = EXCLUDED.credit_cost,
    max_timeout_seconds = EXCLUDED.max_timeout_seconds;
