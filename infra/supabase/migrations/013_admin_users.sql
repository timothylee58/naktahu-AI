-- 013_admin_users.sql
-- Seed primary/secondary admin roles via auth.users app_metadata.
-- Safe to re-run: merges into existing raw_app_meta_data.

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

-- Agent credits for admin test accounts.
INSERT INTO agent_credits (user_id, credits_remaining, credits_used)
SELECT id, 100, 0 FROM auth.users WHERE email = 'hwandaeplus@gmail.com'
ON CONFLICT (user_id) DO UPDATE SET credits_remaining = GREATEST(agent_credits.credits_remaining, 100);

INSERT INTO agent_credits (user_id, credits_remaining, credits_used)
SELECT id, 50, 0 FROM auth.users WHERE email = 'apitest.tim@gmail.com'
ON CONFLICT (user_id) DO UPDATE SET credits_remaining = GREATEST(agent_credits.credits_remaining, 50);
