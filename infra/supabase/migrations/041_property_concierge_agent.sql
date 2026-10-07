-- 041_property_concierge_agent.sql
-- Registers the new "Property Concierge" guided agent (buyer/renter intake,
-- deterministic lead-tier qualification, property-domain RAG citations,
-- shareable brief) in the agents table seeded by 010_agents.sql.
--
-- Scope note: this agent does NOT source or recommend real property
-- listings, and does NOT place any live WhatsApp/call outreach to
-- agencies — neither a listings inventory nor a messaging/telephony
-- provider exists in this codebase. The escalation step generates a
-- ready-to-send brief the user forwards themselves via a client-side
-- wa.me deep link (no backend credentials, no new dependency). See
-- apps/api/app/agents/property_concierge/nodes.py's module docstring.
--
-- Corresponding Python/frontend changes (same PR):
--   - apps/api/app/agents/property_concierge/     new LangGraph module
--     (state.py, nodes.py, graph.py)
--   - apps/api/app/services/agent_runner.py         start/continue/status
--     handlers + AGENT_START_HANDLERS/AGENT_CONTINUE_HANDLERS/
--     AGENT_STATUS_HANDLERS entries
--   - apps/api/app/routers/agents.py                continue-kwargs
--     conditional (user_id + supabase_client, same as
--     retrenchment-navigator)
--   - apps/api/services/agent_registry.py           _fallback_registry() entry
--   - apps/web/src/lib/agents.ts                    WIRED_AGENTS entry
--   - apps/web/src/components/agents/AgentsHub.tsx  per-slug metadata map entry
--   - apps/web/src/app/agents/property-concierge/page.tsx  new page
--   - apps/web/src/lib/i18n/index.tsx               agents.property-concierge.*
--     keys (bm/en/zh)
--
-- Free tier, 0 credits — matches retrenchment-navigator/health-triage/
-- eligibility-agent, consistent with this session's other free civic
-- guided agents.
INSERT INTO agents (name, description, input_schema, plan_required, credit_cost)
VALUES (
    'property-concierge',
    'Guided buyer/renter intake: lead-tier qualification, property RAG citations (tenancy/strata/land title), and a shareable brief.',
    '{}',
    'free',
    0
)
ON CONFLICT (name) DO NOTHING;
