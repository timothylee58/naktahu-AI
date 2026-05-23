-- 003_user_sessions.sql
-- User session history with row-level security.

CREATE TABLE IF NOT EXISTS user_sessions (
    id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id          uuid        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    query            text        NOT NULL,
    language         varchar(2)  NOT NULL,
    domain           varchar(32) NOT NULL,
    response_summary text,
    citations        jsonb       NOT NULL DEFAULT '[]',
    created_at       timestamptz NOT NULL DEFAULT now()
);

-- Index for fetching a user's session history efficiently
CREATE INDEX IF NOT EXISTS user_sessions_user_id_created_at
    ON user_sessions (user_id, created_at DESC);

-- Row-level security — users may only see and insert their own rows.
ALTER TABLE user_sessions ENABLE ROW LEVEL SECURITY;

CREATE POLICY user_sessions_select
    ON user_sessions
    FOR SELECT
    TO authenticated
    USING (auth.uid() = user_id);

CREATE POLICY user_sessions_insert
    ON user_sessions
    FOR INSERT
    TO authenticated
    WITH CHECK (auth.uid() = user_id);
