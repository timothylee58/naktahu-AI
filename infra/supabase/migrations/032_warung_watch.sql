-- 032_warung_watch.sql
-- Warung Watch: crowdsourced live "how busy is it right now" check-ins for
-- Malaysian warungs/kopitiams/food stalls, queried by NakTahu's chat agent
-- when a user asks something like "Is Pelita packed right now?".
--
-- This is deliberately NOT part of the RAG document_chunks pipeline —
-- document_chunks serves pre-ingested, confidence-gated government/
-- institutional text with real citation URLs. Live crowd status is
-- ephemeral, unverifiable in the same way, and has its own freshness
-- window instead of a citation. Two tables:
--
--   warungs          — the place itself (name, free-text location, optional
--                       lat/lng), created on-demand the first time anyone
--                       checks in against a name that doesn't exist yet.
--   warung_checkins  — one row per report. `source` is deliberately an enum
--                       wider than what's wired up today: 'user_report' is
--                       the only source actually being written to at launch
--                       (the crowdsourced check-in flow), 'owner_report' and
--                       'google_popular_times' are reserved for future
--                       ingestion paths (a WhatsApp-based owner toggle, and
--                       a Google Places Popular Times baseline) so the
--                       aggregation query in services/warung_watch.py never
--                       needs another migration just to start reading a
--                       new source type once those exist.

CREATE TABLE IF NOT EXISTS warungs (
    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    name            text        NOT NULL,
    normalized_name text        NOT NULL,
    location        text,
    lat             double precision,
    lng             double precision,
    created_by      uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
    verified        boolean     NOT NULL DEFAULT false,
    created_at      timestamptz NOT NULL DEFAULT now()
);

-- Case/whitespace-insensitive lookup so "Pelita", "pelita ", "PELITA" all
-- resolve to the same warung instead of silently creating duplicates.
CREATE INDEX IF NOT EXISTS warungs_normalized_name_idx
    ON warungs (normalized_name);

CREATE TABLE IF NOT EXISTS warung_checkins (
    id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    warung_id        uuid        NOT NULL REFERENCES warungs(id) ON DELETE CASCADE,
    status           varchar(16) NOT NULL CHECK (status IN ('empty', 'moderate', 'packed')),
    source           varchar(24) NOT NULL DEFAULT 'user_report'
                                  CHECK (source IN ('user_report', 'owner_report', 'google_popular_times')),
    reporter_id      uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
    anon_session_id  text,
    created_at       timestamptz NOT NULL DEFAULT now()
);

-- Backs "most recent N check-ins for this warung within the freshness
-- window" — the actual query services/warung_watch.py runs on every
-- status lookup.
CREATE INDEX IF NOT EXISTS warung_checkins_warung_created_idx
    ON warung_checkins (warung_id, created_at DESC);

-- Public-readable, service-role-writes-only — same convention as
-- shared_answers (015): the FastAPI layer validates/rate-limits, then
-- inserts using the service-role client, so there is no anon/authenticated
-- INSERT policy here.
ALTER TABLE warungs ENABLE ROW LEVEL SECURITY;
ALTER TABLE warung_checkins ENABLE ROW LEVEL SECURITY;

CREATE POLICY warungs_select_all
    ON warungs
    FOR SELECT
    TO anon, authenticated
    USING (true);

CREATE POLICY warung_checkins_select_all
    ON warung_checkins
    FOR SELECT
    TO anon, authenticated
    USING (true);
