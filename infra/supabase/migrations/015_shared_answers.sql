-- 015_shared_answers.sql
-- Shareable answer permalinks. The row id is the public share id — a
-- random UUID (not sequential), so a share link can't be enumerated to
-- harvest other users' shared queries.

CREATE TABLE IF NOT EXISTS shared_answers (
    id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id          uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
    query            text        NOT NULL,
    response_text    text        NOT NULL,
    citations        jsonb       NOT NULL DEFAULT '[]',
    domain           varchar(32) NOT NULL,
    language         varchar(16) NOT NULL,
    confidence       real,
    created_at       timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS shared_answers_created_at
    ON shared_answers (created_at DESC);

-- Unlike feedback/stripe_events, these rows are intentionally public once
-- created — the whole point is a link anyone can open. All writes still go
-- through the API using the service role (no anon/authenticated INSERT
-- policy), but reads are open since the content was deliberately shared.
ALTER TABLE shared_answers ENABLE ROW LEVEL SECURITY;

CREATE POLICY shared_answers_select_all
    ON shared_answers
    FOR SELECT
    TO anon, authenticated
    USING (true);
