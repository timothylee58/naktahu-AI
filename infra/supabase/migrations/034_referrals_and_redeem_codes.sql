-- Referral program (code, share, one-time reward) and redeem codes
-- (credit top-up or temporary plan trial), backing the "Refer a Friend" /
-- "Give Feedback" / "Redeem code" cards on the profile page.
--
-- Design note on plan grants: this does NOT add a live per-request
-- entitlement check (that would mean an extra Supabase read on every
-- authenticated request across the whole app — services/auth.py's
-- get_current_user is pure JWT decode today, no DB access, and every
-- other authenticated route depends on that staying cheap). Instead, a
-- referral/redeem-code plan grant is written directly into the user's JWT
-- app_metadata.plan via the same admin-API mechanism Stripe subscriptions
-- already use (services/billing.py::_set_plan) — plan_grants below is the
-- record of what plan to revert to and when, checked lazily by
-- GET /api/v1/billing/plan-status (called from the profile page on load),
-- not by a cron job. Acceptable for a free-trial grant: worst case is a
-- short window of extra access after expiry until the user next opens
-- their profile, not a security or billing-correctness issue.
--
-- Files touched in this PR: this migration, apps/api/services/referral.py
-- (new), apps/api/services/redeem_codes.py (new), apps/api/routers/referrals.py
-- (new, mounted in both main.py and app/main.py), apps/api/routers/billing.py
-- (redeem + plan-status endpoints), apps/web/src/app/profile/page.tsx.

CREATE TABLE IF NOT EXISTS referral_codes (
  user_id uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  code text UNIQUE NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

-- One referral relationship per referred user — referred_user_id as the
-- primary key enforces "a user can only ever be referred once" without a
-- separate unique constraint.
CREATE TABLE IF NOT EXISTS referrals (
  referred_user_id uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  referrer_user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  code text NOT NULL,
  status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'completed')),
  created_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz,
  CONSTRAINT referrals_no_self_referral CHECK (referred_user_id <> referrer_user_id)
);

-- Admin-seeded for now (manually inserted via SQL — no admin UI in this
-- pass). Redeemable for either a credit top-up or a temporary plan grant.
CREATE TABLE IF NOT EXISTS redeem_codes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  code text UNIQUE NOT NULL,
  kind text NOT NULL CHECK (kind IN ('credits', 'plan_trial')),
  credits_amount int,
  plan_tier text,
  plan_duration_days int,
  max_uses int,
  uses_count int NOT NULL DEFAULT 0,
  expires_at timestamptz,
  active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT redeem_codes_kind_fields CHECK (
    (kind = 'credits' AND credits_amount IS NOT NULL) OR
    (kind = 'plan_trial' AND plan_tier IS NOT NULL AND plan_duration_days IS NOT NULL)
  )
);

-- Claim-first idempotency: one redemption per (code, user) pair — same
-- insert-first-via-unique-constraint pattern as services/billing.py's
-- mark_event_processed (Trap #8), not check-then-insert, so a concurrent
-- double-submit of the same code by the same user can't double-grant.
CREATE TABLE IF NOT EXISTS redeem_code_redemptions (
  redeem_code_id uuid NOT NULL REFERENCES redeem_codes(id) ON DELETE CASCADE,
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (redeem_code_id, user_id)
);

CREATE TABLE IF NOT EXISTS plan_grants (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  plan_tier text NOT NULL,
  previous_plan text NOT NULL,
  source text NOT NULL CHECK (source IN ('referral', 'redeem_code')),
  source_id uuid,
  expires_at timestamptz NOT NULL,
  reverted_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (source, source_id, user_id)
);

ALTER TABLE referral_codes ENABLE ROW LEVEL SECURITY;
ALTER TABLE referrals ENABLE ROW LEVEL SECURITY;
ALTER TABLE redeem_codes ENABLE ROW LEVEL SECURITY;
ALTER TABLE redeem_code_redemptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE plan_grants ENABLE ROW LEVEL SECURITY;

CREATE POLICY "own referral code" ON referral_codes
  FOR SELECT TO authenticated USING (auth.uid() = user_id);

CREATE POLICY "own referrals" ON referrals
  FOR SELECT TO authenticated USING (auth.uid() = referrer_user_id OR auth.uid() = referred_user_id);

CREATE POLICY "own plan grants" ON plan_grants
  FOR SELECT TO authenticated USING (auth.uid() = user_id);

-- redeem_codes / redeem_code_redemptions: no policy for authenticated/anon
-- is intentional — RLS denies by default, and every read/write here goes
-- through the backend's service-role client. A redeem code's existence,
-- remaining uses, or expiry must not be directly queryable by a client.
