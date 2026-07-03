-- 008_hitpay_events.sql
-- Webhook idempotency ledger for HitPay (FPX/DuitNow QR), scoped to agent
-- credit-pack checkout only — see apps/api/services/billing.py. HitPay's
-- payment_id is not comparable to a Stripe event id, so it gets its own
-- table rather than sharing stripe_events (007_billing.sql).

CREATE TABLE IF NOT EXISTS hitpay_events (
    id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    hitpay_payment_id text       NOT NULL UNIQUE,
    processed_at     timestamptz NOT NULL DEFAULT now()
);

-- No client-facing read path — internal idempotency ledger only. RLS
-- enabled with no policies means it's unreadable/unwritable except via the
-- service role, same as stripe_events.
ALTER TABLE hitpay_events ENABLE ROW LEVEL SECURITY;
