-- 064_user_notes.sql
-- Personal notes: a signed-in user's own markdown notes, optionally saved from
-- an answer, searchable with Postgres full-text search.
--
-- PRIVACY: owner-only RLS, no anon/public policy. These are the user's own
-- words; they are never mixed into the public document_chunks corpus and are
-- never used to answer anyone else's question.
--
-- NOTE: the API uses the service-role client (RLS bypassed), so the router
-- filters every query on the caller's user_id; the policies below guard any
-- direct client access.
--
-- Search is keyword-based (tsvector, 'simple' config so Malay/English/Chinese
-- words are not stemmed away). Tags are filtered separately because
-- array_to_string is not immutable and cannot be in a generated column.

CREATE TABLE IF NOT EXISTS user_notes (
    id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     uuid        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    title       text        NOT NULL CHECK (char_length(title) BETWEEN 1 AND 200),
    body        text        NOT NULL DEFAULT '' CHECK (char_length(body) <= 20000),
    tags        text[]      NOT NULL DEFAULT '{}' CHECK (cardinality(tags) <= 10),
    -- Set when the note was saved from an answer: {query, citations[], saved_at}.
    source      jsonb,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    search_tsv  tsvector GENERATED ALWAYS AS (
        to_tsvector('simple', coalesce(title, '') || ' ' || coalesce(body, ''))
    ) STORED
);

CREATE INDEX IF NOT EXISTS user_notes_user_updated ON user_notes (user_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS user_notes_tsv ON user_notes USING GIN (search_tsv);
CREATE INDEX IF NOT EXISTS user_notes_tags ON user_notes USING GIN (tags);

ALTER TABLE user_notes ENABLE ROW LEVEL SECURITY;

CREATE POLICY user_notes_select ON user_notes
    FOR SELECT TO authenticated USING (auth.uid() = user_id);
CREATE POLICY user_notes_insert ON user_notes
    FOR INSERT TO authenticated WITH CHECK (auth.uid() = user_id);
CREATE POLICY user_notes_update ON user_notes
    FOR UPDATE TO authenticated USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);
CREATE POLICY user_notes_delete ON user_notes
    FOR DELETE TO authenticated USING (auth.uid() = user_id);
