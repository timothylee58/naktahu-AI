-- 007_billing.sql
-- Stripe-backed freemium billing: agent credit ledger + webhook idempotency.
-- Plan itself (free/student/pro/business) is NOT stored here — it lives in
-- auth.users.app_metadata, set via the Supabase admin API on checkout
-- completion (see apps/api/services/billing.py), and read straight off the
-- JWT app_metadata claim by the API. That keeps plan checks a pure JWT
-- decode with no extra DB round-trip on every gated request.

CREATE TABLE IF NOT EXISTS agent_credits (
    id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id          uuid        NOT NULL UNIQUE REFERENCES auth.users(id) ON DELETE CASCADE,
    credits_remaining int        NOT NULL DEFAULT 0,
    credits_used     int         NOT NULL DEFAULT 0,
    last_topup       timestamptz
);

CREATE TABLE IF NOT EXISTS stripe_events (
    id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    stripe_event_id  text        NOT NULL UNIQUE,
    processed_at     timestamptz NOT NULL DEFAULT now()
);

-- Row-level security. All writes go through the API using the service role
-- key, which bypasses RLS — these policies only govern direct client reads.
ALTER TABLE agent_credits ENABLE ROW LEVEL SECURITY;

CREATE POLICY agent_credits_select_own
    ON agent_credits
    FOR SELECT
    TO authenticated
    USING (auth.uid() = user_id);

-- stripe_events has no client-facing read path — it's an internal
-- idempotency ledger, not user-visible data. RLS enabled with no policies
-- means it's unreadable and unwritable except via the service role.
ALTER TABLE stripe_events ENABLE ROW LEVEL SECURITY;

-- Atomic upsert for credit top-ups. A plain select-then-update/insert from
-- the API would race under concurrent webhook deliveries (two deliveries
-- reading the same "current" balance and each writing current+n, losing one
-- top-up). INSERT ... ON CONFLICT does the read-modify-write as a single
-- statement under the row lock, so concurrent calls always sum correctly.
CREATE OR REPLACE FUNCTION add_agent_credits(
    p_user_id uuid,
    p_amount  int,
    p_now     timestamptz
) RETURNS void AS $$
BEGIN
    INSERT INTO agent_credits (user_id, credits_remaining, credits_used, last_topup)
    VALUES (p_user_id, p_amount, 0, p_now)
    ON CONFLICT (user_id)
    DO UPDATE SET
        credits_remaining = agent_credits.credits_remaining + EXCLUDED.credits_remaining,
        last_topup = EXCLUDED.last_topup;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
