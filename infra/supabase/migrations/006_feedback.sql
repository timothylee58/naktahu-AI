-- 006_feedback.sql
-- Thumbs up/down feedback on assistant answers. Supports anonymous users
-- (user_id nullable) since answer quality signal matters regardless of auth.
-- Feeds two consumers: analytics dashboards, and negative-rated rows as
-- candidate additions to the eval harness (apps/api/evals/).

CREATE TABLE IF NOT EXISTS feedback (
    id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id          uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
    session_id       text        NOT NULL,
    query            text        NOT NULL,
    response_summary text        NOT NULL,
    citations        jsonb       NOT NULL DEFAULT '[]',
    domain           varchar(32) NOT NULL,
    language         varchar(2)  NOT NULL,
    rating           smallint    NOT NULL CHECK (rating IN (-1, 1)),
    created_at       timestamptz NOT NULL DEFAULT now()
);

-- Mining negative feedback for eval candidates is the primary read pattern.
CREATE INDEX IF NOT EXISTS feedback_rating_created_at
    ON feedback (rating, created_at DESC);

CREATE INDEX IF NOT EXISTS feedback_domain
    ON feedback (domain);

-- Row-level security. All writes go through the API using the service role
-- key, which bypasses RLS — these policies only govern direct client access
-- and intentionally have no anon/authenticated INSERT policy, so a browser
-- cannot write a feedback row by calling Supabase directly.
ALTER TABLE feedback ENABLE ROW LEVEL SECURITY;

CREATE POLICY feedback_select_own
    ON feedback
    FOR SELECT
    TO authenticated
    USING (auth.uid() = user_id);
