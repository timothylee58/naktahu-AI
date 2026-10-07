-- 044_api_keys_free_plan_and_name.sql
-- Fixes a live gap: api_keys.plan's CHECK constraint (migration 014) never
-- included 'free' — only 'starter', 'growth', 'enterprise', 'widget',
-- 'white_label'. But 'free' has been the Developer API's default,
-- freemium-for-any-signed-in-user plan since routers/developer.py's
-- CreateKeyRequest.plan Literal and services/api_key_service.py's
-- API_PLAN_DEFAULTS/VALID_API_PLANS were written, and it's the plan
-- pre-selected in the frontend's /developer page (PLANS[0]). Every attempt
-- to create a free-tier key has therefore been rejected at the database
-- layer (constraint violation), regardless of what the app-layer
-- validation allowed through — the most common path a new developer hits
-- first has been broken since 'free' was introduced. Widening the
-- constraint to match the application's actual VALID_API_PLANS set.
--
-- Also adds an optional `name` column so a user with multiple keys (up to
-- MAX_KEYS_PER_USER=3) can label them ("prod", "staging widget", ...)
-- instead of only distinguishing by plan + creation date.
ALTER TABLE api_keys DROP CONSTRAINT IF EXISTS api_keys_plan_check;
ALTER TABLE api_keys ADD CONSTRAINT api_keys_plan_check CHECK (
    plan IN ('free', 'starter', 'growth', 'enterprise', 'widget', 'white_label')
);

ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS name text CHECK (name IS NULL OR char_length(name) <= 60);
