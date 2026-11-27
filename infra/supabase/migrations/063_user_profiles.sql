-- 063_user_profiles.sql
-- Saved "about you" profile, so agents can prefill what the user already told us
-- instead of asking again (the grant-finder re-entry problem, everywhere).
--
-- WHAT: one row per user holding a few self-declared facts. Every column is
-- optional; the user chooses what to share, can edit it, and can delete it.
--
-- PRIVACY: owner-only RLS, no anon/public policy (modelled on investor_profiles,
-- migration 022). is_bumiputera is an opt-in sensitive field: NULL means "not
-- shared", and it is never inferred. Rows cascade-delete with the auth user.
--
-- NOTE: the API reaches this table with the service-role client (RLS bypassed),
-- so the router itself filters on the caller's user_id; these policies are the
-- defence for any direct client access.

CREATE TABLE IF NOT EXISTS user_profiles (
    user_id           uuid        PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    state             text        CHECK (state IN (
        'johor','kedah','kelantan','melaka','negeri_sembilan','pahang','penang','perak',
        'perlis','sabah','sarawak','selangor','terengganu','kl','labuan','putrajaya')),
    postcode          char(5)     CHECK (postcode ~ '^[0-9]{5}$'),
    employment_status text        CHECK (employment_status IN (
        'employed','self_employed','unemployed','retired','student')),
    business_type     text        CHECK (business_type IN (
        'sole_prop','sdn_bhd','startup','llp','cooperative')),
    sector            text        CHECK (sector IN (
        'technology','ai','fintech','edtech','healthtech','digital','deeptech','biotech',
        'manufacturing','agriculture','services')),
    household_size    smallint    CHECK (household_size BETWEEN 1 AND 30),
    is_bumiputera     boolean,
    updated_at        timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;

CREATE POLICY user_profiles_select ON user_profiles
    FOR SELECT TO authenticated USING (auth.uid() = user_id);
CREATE POLICY user_profiles_insert ON user_profiles
    FOR INSERT TO authenticated WITH CHECK (auth.uid() = user_id);
CREATE POLICY user_profiles_update ON user_profiles
    FOR UPDATE TO authenticated USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);
CREATE POLICY user_profiles_delete ON user_profiles
    FOR DELETE TO authenticated USING (auth.uid() = user_id);
