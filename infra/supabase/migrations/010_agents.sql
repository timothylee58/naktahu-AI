-- 010_agents.sql
-- Product-agent registry, session checkpoints, run audit log, generated
-- documents, and regulatory deadline calendar for Deadline Monitor.

CREATE TABLE IF NOT EXISTS agents (
    id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    name          text        NOT NULL UNIQUE,
    description   text        NOT NULL DEFAULT '',
    input_schema  jsonb       NOT NULL DEFAULT '{}',
    plan_required text        NOT NULL DEFAULT 'free',
    credit_cost   int         NOT NULL DEFAULT 0,
    created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS agent_sessions (
    id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       uuid        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    agent_name    text        NOT NULL REFERENCES agents(name) ON DELETE CASCADE,
    checkpoint    jsonb       NOT NULL DEFAULT '{}',
    updated_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS agent_sessions_user_agent_idx
    ON agent_sessions (user_id, agent_name);

CREATE TABLE IF NOT EXISTS agent_runs (
    id                uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           uuid        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    agent_name        text        NOT NULL,
    session_id        uuid        REFERENCES agent_sessions(id) ON DELETE SET NULL,
    input             jsonb       NOT NULL DEFAULT '{}',
    output            jsonb       NOT NULL DEFAULT '{}',
    turns_count       int         NOT NULL DEFAULT 0,
    tool_calls        jsonb       NOT NULL DEFAULT '[]',
    completion_status text        NOT NULL DEFAULT 'running',
    latency_ms        int,
    created_at        timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS agent_runs_user_created_idx
    ON agent_runs (user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS generated_documents (
    id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       uuid        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    agent_type    text        NOT NULL,
    storage_path  text        NOT NULL,
    signed_url    text,
    url_expires_at timestamptz,
    created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS deadline_schedule (
    id             uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    domain         text        NOT NULL,
    deadline_name  text        NOT NULL,
    due_date       date        NOT NULL,
    recurrence     text,
    source_url     text        NOT NULL,
    last_verified  timestamptz NOT NULL DEFAULT now(),
    UNIQUE (domain, deadline_name, due_date)
);

CREATE INDEX IF NOT EXISTS deadline_schedule_due_date_idx
    ON deadline_schedule (due_date);

-- Seed product agents (idempotent).
INSERT INTO agents (name, description, input_schema, plan_required, credit_cost) VALUES
(
    'compliance-drafter',
    'Multi-domain PDF compliance report with HITL gate before generation.',
    '{"type":"object","properties":{"business_type":{"type":"string"},"domains":{"type":"array","items":{"type":"string"}},"context":{"type":"string"}}}',
    'free',
    1
),
(
    'deadline-monitor',
    'Regulatory deadline calendar with proactive alerts.',
    '{}',
    'pro',
    0
),
(
    'study-agent',
    'SPM past-paper upload with education RAG explanations.',
    '{}',
    'student',
    0
),
(
    'immigration-navigator',
    'Conversational visa intake with immigration RAG.',
    '{}',
    'free',
    1
),
(
    'health-triage',
    'BM symptom intake with KKM facility recommendations.',
    '{}',
    'free',
    0
),
(
    'research-synthesiser',
    'Parallel multi-domain RAG synthesis for API Growth tier.',
    '{}',
    'business',
    0
)
ON CONFLICT (name) DO NOTHING;

-- Seed Malaysian regulatory deadlines (illustrative — verified by nightly cron).
INSERT INTO deadline_schedule (domain, deadline_name, due_date, recurrence, source_url) VALUES
('tax', 'CP204 estimate submission', '2026-06-30', 'annual', 'https://www.hasil.gov.my'),
('tax', 'Form BE filing', '2026-04-30', 'annual', 'https://www.hasil.gov.my'),
('epf', 'Employer contribution deadline', '2026-07-15', 'monthly', 'https://www.kwsp.gov.my'),
('business', 'SSM annual return', '2026-11-30', 'annual', 'https://www.ssm.com.my'),
('tax', 'SST return filing', '2026-07-31', 'monthly', 'https://www.hasil.gov.my')
ON CONFLICT (domain, deadline_name, due_date) DO NOTHING;

-- Atomic credit deduction. Returns remaining balance, or -1 if insufficient.
CREATE OR REPLACE FUNCTION deduct_agent_credits(
    p_user_id uuid,
    p_amount  int
) RETURNS int AS $$
DECLARE
    v_remaining int;
BEGIN
    UPDATE agent_credits
    SET
        credits_remaining = credits_remaining - p_amount,
        credits_used      = credits_used + p_amount
    WHERE user_id = p_user_id
      AND credits_remaining >= p_amount
    RETURNING credits_remaining INTO v_remaining;

    IF NOT FOUND THEN
        RETURN -1;
    END IF;
    RETURN v_remaining;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

ALTER TABLE agents ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE generated_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE deadline_schedule ENABLE ROW LEVEL SECURITY;

-- Read-only deadline calendar for authenticated users.
CREATE POLICY deadline_schedule_select_authenticated
    ON deadline_schedule FOR SELECT TO authenticated USING (true);
