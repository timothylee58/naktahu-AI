-- 013_admin_users.sql
-- Seed primary/secondary admin roles via auth.users app_metadata.
-- Safe to re-run: merges into existing raw_app_meta_data.
-- Creates agent_credits if 007_billing.sql has not been applied yet.

CREATE TABLE IF NOT EXISTS agent_credits (
    id                uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           uuid        NOT NULL UNIQUE REFERENCES auth.users(id) ON DELETE CASCADE,
    credits_remaining int         NOT NULL DEFAULT 0,
    credits_used      int         NOT NULL DEFAULT 0,
    last_topup        timestamptz
);

ALTER TABLE agent_credits ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS agent_credits_select_own ON agent_credits;
CREATE POLICY agent_credits_select_own
    ON agent_credits
    FOR SELECT
    TO authenticated
    USING (auth.uid() = user_id);

UPDATE auth.users
SET raw_app_meta_data = COALESCE(raw_app_meta_data, '{}'::jsonb) || jsonb_build_object(
    'plan', 'business',
    'role', 'primary_admin'
)
WHERE email = 'hwandaeplus@gmail.com';

UPDATE auth.users
SET raw_app_meta_data = COALESCE(raw_app_meta_data, '{}'::jsonb) || jsonb_build_object(
    'plan', 'business',
    'role', 'secondary_admin'
)
WHERE email = 'apitest.tim@gmail.com';

INSERT INTO agent_credits (user_id, credits_remaining, credits_used)
SELECT id, 100, 0 FROM auth.users WHERE email = 'hwandaeplus@gmail.com'
ON CONFLICT (user_id) DO UPDATE SET credits_remaining = GREATEST(agent_credits.credits_remaining, 100);

INSERT INTO agent_credits (user_id, credits_remaining, credits_used)
SELECT id, 50, 0 FROM auth.users WHERE email = 'apitest.tim@gmail.com'
ON CONFLICT (user_id) DO UPDATE SET credits_remaining = GREATEST(agent_credits.credits_remaining, 50);
