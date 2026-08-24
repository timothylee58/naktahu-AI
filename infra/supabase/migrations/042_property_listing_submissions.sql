-- 042_property_listing_submissions.sql
-- User-submitted property listings for the Property Concierge agent
-- (property_concierge doesn't scrape/source live listings itself — see its
-- module docstring — this is the legitimate alternative: the USER pastes a
-- listing URL + details they found themselves. Stored as unverified,
-- never presented as an official or agent-sourced fact.)
--
-- Reward model: submitting a NEW listing (first time this user has
-- submitted this exact URL) earns a disclosed credit bonus — the incentive
-- is stated on the submission form itself (apps/web/src/app/agents/
-- property-concierge/page.tsx), not concealed. UNIQUE(user_id, url) below
-- is what makes the credit award idempotent: re-submitting the same URL
-- is a silent no-op (ON CONFLICT DO NOTHING in
-- services/property_submissions.py), so a user can't farm credits by
-- resubmitting one listing.
CREATE TABLE IF NOT EXISTS property_listing_submissions (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    url             text NOT NULL CHECK (char_length(url) BETWEEN 8 AND 500),
    title           text CHECK (char_length(title) <= 200),
    price_myr       numeric(12, 2) CHECK (price_myr IS NULL OR price_myr >= 0),
    location        text CHECK (char_length(location) <= 120),
    property_type   text CHECK (property_type IS NULL OR property_type IN ('condo', 'apartment', 'landed', 'other')),
    bedrooms         smallint CHECK (bedrooms IS NULL OR bedrooms BETWEEN 0 AND 50),
    notes           text CHECK (char_length(notes) <= 1000),
    status          text NOT NULL DEFAULT 'unverified' CHECK (status IN ('unverified', 'flagged', 'removed')),
    credit_awarded  boolean NOT NULL DEFAULT false,
    created_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id, url)
);

CREATE INDEX IF NOT EXISTS idx_property_listing_submissions_user
    ON property_listing_submissions (user_id, created_at DESC);

ALTER TABLE property_listing_submissions ENABLE ROW LEVEL SECURITY;

-- A submitter can see and manage only their own submissions — this is
-- unverified user content, never surfaced as a public directory. Service
-- role (server-side inserts/reads via the backend) bypasses RLS as usual.
CREATE POLICY "property_listing_submissions_select_own"
    ON property_listing_submissions FOR SELECT
    TO authenticated
    USING (auth.uid() = user_id);

CREATE POLICY "property_listing_submissions_insert_own"
    ON property_listing_submissions FOR INSERT
    TO authenticated
    WITH CHECK (auth.uid() = user_id);
