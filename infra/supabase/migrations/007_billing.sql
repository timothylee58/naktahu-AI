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
