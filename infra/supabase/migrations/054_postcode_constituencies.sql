-- 054_postcode_constituencies.sql
-- Postcode -> parliamentary constituency crosswalk, so the landing page's
-- postcode box can show the visitor's actual MP (and office contact from
-- migration 049) instead of only their state.
--
-- Until now there was no way to go from a postcode to a seat: mp_profiles is
-- keyed by constituency_code, and the frontend's postcode lookup only knows
-- the Pos Malaysia prefix -> state table (apps/web/src/lib/postcode.ts).
--
-- One postcode can straddle several seats, so the key is the PAIR, and the
-- API returns every MP for a postcode rather than guessing one. Each row
-- records where the mapping came from (`source`) so a disputed mapping can be
-- traced and re-loaded. Rows are loaded only from a real dataset by
-- scripts/ingest_parliament/seed_postcode_seats.py — never hand-entered or
-- inferred, because a wrong mapping shows a visitor the wrong MP.
--
-- Until data is loaded the table is empty, the lookup returns no MPs, and
-- the frontend falls back to the state-only line it shows today.

CREATE TABLE IF NOT EXISTS postcode_constituencies (
    postcode           char(5) NOT NULL CHECK (postcode ~ '^[0-9]{5}$'),
    constituency_code  text    NOT NULL,
    source             text    NOT NULL,
    updated_at         timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (postcode, constituency_code)
);

CREATE INDEX IF NOT EXISTS idx_postcode_constituencies_code
    ON postcode_constituencies (constituency_code);

-- Public reference data, same as mp_profiles/constituencies (migration 025):
-- readable by everyone, writable only by the service role (which bypasses RLS).
ALTER TABLE postcode_constituencies ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "postcode_constituencies_public_read" ON postcode_constituencies;
CREATE POLICY "postcode_constituencies_public_read"
    ON postcode_constituencies FOR SELECT TO anon, authenticated USING (true);
