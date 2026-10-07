-- Managed leads captured from /perniagaan-terurus, the manual-sale landing
-- page for the "kami uruskan pematuhan & geran anda" (Pro-Perniagaan +
-- Kredit Ejen, sold as a managed service, not self-serve checkout) offer.
--
-- Deliberately NOT reusing referral_codes/referrals (migration 034) — those
-- tables mean a specific, different thing: an existing NakTahu user
-- referring another user into a peer reward program (referrer_user_id/
-- referred_user_id both auth.users). This is external partner attribution
-- (a company-secretary/accountant forwarding this page's link) captured
-- from an anonymous visitor who has no NakTahu account yet — a plain text
-- tag, not a relationship between two users. Kept as its own table on
-- purpose.
--
-- application_status doubles as both "where is this lead in the funnel"
-- (lead -> contacted) AND, once someone becomes an actual managed client,
-- "where is their compliance/grant application" (draft -> submitted ->
-- approved/rejected) — one manually-updated internal status field for the
-- first 3-5 pilot clients, not a client-facing feature (per the kickstart
-- plan: validate demand manually before building the automated status
-- view). No separate "clients" table exists yet to split this into; this
-- table doubles as that until the managed-client pilot proves out demand
-- (see graph.py-adjacent docstring style: this note documents a scope
-- decision, not a TODO to chase).
--
-- No SELECT/INSERT policy for anon/authenticated is intentional, matching
-- redeem_codes' documented reasoning (034): RLS enabled with zero policies
-- denies by default, and every read/write goes through the backend's
-- service-role client (POST /api/v1/leads, services/leads.py) so lead PII
-- (name, email/phone, message) is never directly queryable by a client.

CREATE TABLE IF NOT EXISTS managed_leads (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name               text NOT NULL,
  company            text,
  contact_email      text,
  contact_phone      text,
  message            text,
  referral_source    text,          -- free-text partner tag from ?ref= on the landing page
  application_status text NOT NULL DEFAULT 'lead'
    CHECK (application_status IN ('lead', 'contacted', 'draft', 'submitted', 'approved', 'rejected')),
  status_updated_at  timestamptz,
  created_at         timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT managed_leads_has_contact CHECK (contact_email IS NOT NULL OR contact_phone IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_managed_leads_referral_source ON managed_leads(referral_source);
CREATE INDEX IF NOT EXISTS idx_managed_leads_status ON managed_leads(application_status);
CREATE INDEX IF NOT EXISTS idx_managed_leads_created ON managed_leads(created_at DESC);

ALTER TABLE managed_leads ENABLE ROW LEVEL SECURITY;
-- No policies — service-role only, see module comment above.
