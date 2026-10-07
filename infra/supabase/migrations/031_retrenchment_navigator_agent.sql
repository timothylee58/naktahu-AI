-- 031_retrenchment_navigator_agent.sql
-- Registers the new "Options after Retrenchment" guided agent (EIS claim
-- eligibility, statutory termination benefits under the Employment Act 1955
-- Second Schedule, notice-period rights, next-steps checklist) in the
-- agents table seeded by 010_agents.sql.
--
-- Corresponding Python/frontend changes (same PR):
--   - apps/api/app/agents/retrenchment_navigator/  new LangGraph module
--     (state.py, nodes.py, graph.py)
--   - apps/api/app/services/agent_runner.py         start/continue/status
--     handlers + AGENT_START_HANDLERS/AGENT_CONTINUE_HANDLERS/
--     AGENT_STATUS_HANDLERS entries
--   - apps/api/app/routers/agents.py                continue-kwargs
--     conditional (user_id + supabase_client, same as immigration-navigator)
--   - apps/api/services/agent_registry.py           _fallback_registry() entry
--   - apps/web/src/lib/agents.ts                    WIRED_AGENTS entry
--   - apps/web/src/components/agents/AgentsHub.tsx  per-slug metadata map entry
--   - apps/web/src/app/agents/retrenchment-navigator/page.tsx  new page
--   - apps/web/src/lib/i18n/index.tsx               agents.retrenchment-navigator.*
--     keys (bm/en/zh)
--
-- Free tier, 0 credits — matches health-triage and eligibility-agent
-- (not immigration-navigator's credit-on-complete model), per product
-- decision made when planning this feature.
INSERT INTO agents (name, description, input_schema, plan_required, credit_cost)
VALUES (
    'retrenchment-navigator',
    'Guided retrenchment options: EIS claim eligibility, statutory termination benefits, and next-steps checklist.',
    '{}',
    'free',
    0
)
ON CONFLICT (name) DO NOTHING;
