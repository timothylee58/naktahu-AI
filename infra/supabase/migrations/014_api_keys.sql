-- 014_api_keys.sql — Developer API keys, metering events, RLS

CREATE TABLE IF NOT EXISTS api_keys (
    id                  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             uuid        NOT NULL REFERENCES auth.users (id) ON DELETE CASCADE,
    key_hash            text        NOT NULL UNIQUE,
    key_prefix          text        NOT NULL,
    plan                text        NOT NULL DEFAULT 'starter'
        CHECK (plan IN ('starter', 'growth', 'enterprise', 'widget', 'white_label')),
    calls_used          int         NOT NULL DEFAULT 0,
    calls_limit         int         NOT NULL DEFAULT 5500,
    rate_limit_per_min  int         NOT NULL DEFAULT 10,
    domain_whitelist    text[]      NOT NULL DEFAULT '{}',
    active              boolean     NOT NULL DEFAULT true,
    last_used_at        timestamptz,
    created_at          timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS api_keys_user_id_idx ON api_keys (user_id);
CREATE INDEX IF NOT EXISTS api_keys_key_hash_idx ON api_keys (key_hash);
CREATE INDEX IF NOT EXISTS api_keys_active_idx ON api_keys (active) WHERE active = true;

CREATE TABLE IF NOT EXISTS api_key_events (
    id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    key_id      uuid        NOT NULL REFERENCES api_keys (id) ON DELETE CASCADE,
    endpoint    text        NOT NULL,
    domain      text,
    response_ms int,
    cache_hit   boolean     NOT NULL DEFAULT false,
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS api_key_events_key_id_idx ON api_key_events (key_id);
CREATE INDEX IF NOT EXISTS api_key_events_created_at_idx ON api_key_events (created_at DESC);

ALTER TABLE api_keys ENABLE ROW LEVEL SECURITY;
ALTER TABLE api_key_events ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS api_keys_select_own ON api_keys;
CREATE POLICY api_keys_select_own
    ON api_keys FOR SELECT
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS api_keys_insert_own ON api_keys;
CREATE POLICY api_keys_insert_own
    ON api_keys FOR INSERT
    WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS api_keys_update_own ON api_keys;
CREATE POLICY api_keys_update_own
    ON api_keys FOR UPDATE
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS api_keys_delete_own ON api_keys;
CREATE POLICY api_keys_delete_own
    ON api_keys FOR DELETE
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS api_key_events_select_own ON api_key_events;
CREATE POLICY api_key_events_select_own
    ON api_key_events FOR SELECT
    USING (
        key_id IN (SELECT id FROM api_keys WHERE user_id = auth.uid())
    );
