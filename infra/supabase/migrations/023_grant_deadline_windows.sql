-- 023_grant_deadline_windows.sql
-- Deadline Monitor extension: bridge grant_database application windows into
-- deadline_schedule (the ONE calendar table the cron already reads), plus
-- Pro-plan alert SUBSCRIPTIONS and a dedup ledger so alerts can actually be
-- emailed instead of only logged.
--
-- Why bridge, not duplicate: deadline_schedule is canonical (010_agents.sql).
-- We do NOT create a parallel grant_deadlines table. grant_database rows with
-- a fixed application_deadline are backfilled into deadline_schedule under
-- domain='business', and a trigger keeps that in sync going forward whenever
-- application_deadline changes (e.g. re-verification by ingest/admin tooling)
-- so this migration is more than a one-time backfill that would go stale.
-- A DB trigger was chosen over an application-level sync step in the cron
-- script because the write path for grant_database is not owned by this
-- cron script alone (ingestion/admin updates too) and a trigger guarantees
-- deadline_schedule can never drift regardless of which code path writes
-- application_deadline.
--
-- deadline_schedule's existing UNIQUE(domain, deadline_name, due_date) is
-- sufficient to avoid ambiguity for the backfill: domain='business' +
-- deadline_name=programme_name + due_date=application_deadline uniquely
-- identifies a grant deadline row, so no new column on deadline_schedule is
-- needed for the backfill/upsert itself. No FK back to grant_database.id is
-- added either — deadline_schedule is deliberately source-agnostic (it also
-- holds hand-seeded LHDN/EPF/SSM deadlines with no owning table), and a
-- nullable FK would only serve the trigger's own bookkeeping, which the
-- trigger accomplishes fine via the natural key above (upsert matched on the
-- unique constraint, not a foreign key).
--
-- Subscription model — domain-wide, not per-deadline: a founder does not
-- know to subscribe to a specific grant they have never heard of; the whole
-- pitch of Deadline Monitor is surfacing windows they didn't know existed.
-- Per-deadline opt-in cannot deliver that value, so deadline_alert_subscriptions
-- subscribes a user to an entire domain (e.g. 'business') and they receive
-- every deadline_schedule row in that domain. The CHECK constraint reuses
-- the canonical 10-domain list from migration 016_widen_domain_constraint.sql
-- (this is now the 4th site carrying that list — see Trap #6 in CLAUDE.md —
-- but it is a subscription filter, not RAG/router logic, so it does not need
-- to be authoritative; it only needs to reject nonsense domains at signup).
--
-- Dedup — separate ledger table, not a jsonb column: deadline_alert_sends
-- uses a composite PRIMARY KEY(subscription_id, deadline_schedule_id,
-- alert_day) so "have we already sent this alert" is answered by a
-- constraint, not a read-then-write on a jsonb blob. This avoids the exact
-- race class Trap #9 warns about for agent_credits. deadline_alert_sends
-- has NO anon/authenticated RLS policies at all — only the cron script,
-- which runs as the Supabase service role (bypasses RLS entirely), ever
-- touches it, so there is no client-facing access to grant and RLS merely
-- has to be enabled (satisfying "RLS enabled on every new table") without a
-- policy that would otherwise default-deny anyway.
--
-- Delivery channel — email only, via the existing Resend-backed send_email()
-- in app/agents/tools.py. WhatsApp/SMS/Twilio or any other comms provider is
-- explicitly out of scope for this change.
--
-- Degrade-gracefully: none of this is applied until a human pastes this file
-- into the Supabase SQL editor. Until then, subscription queries the cron
-- script makes against deadline_alert_subscriptions/deadline_alert_sends
-- return empty/error paths the script treats as "no subscribers" — it must
-- never crash on a missing table (see deadline_monitor.py's guards).

-- ── 1. Trigger: keep deadline_schedule in sync with grant_database ─────────
CREATE OR REPLACE FUNCTION sync_grant_deadline_to_schedule()
RETURNS trigger AS $$
BEGIN
    INSERT INTO deadline_schedule (domain, deadline_name, due_date, recurrence, source_url, last_verified)
    VALUES ('business', NEW.programme_name, NEW.application_deadline, NULL, NEW.application_url, now())
    ON CONFLICT (domain, deadline_name, due_date) DO UPDATE SET
        source_url    = EXCLUDED.source_url,
        last_verified = EXCLUDED.last_verified;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS grant_database_sync_deadline ON grant_database;
CREATE TRIGGER grant_database_sync_deadline
    AFTER INSERT OR UPDATE OF application_deadline ON grant_database
    FOR EACH ROW
    WHEN (NEW.deadline_is_rolling = false AND NEW.application_deadline IS NOT NULL)
    EXECUTE FUNCTION sync_grant_deadline_to_schedule();

-- ── 2. One-time backfill for the 10 already-seeded Budget 2026 programmes ──
-- (source_url falls back to application_url since grant_database has no
-- separate source_url populated for most rows; source_url is NOT NULL on
-- deadline_schedule.)
INSERT INTO deadline_schedule (domain, deadline_name, due_date, recurrence, source_url, last_verified)
SELECT
    'business',
    programme_name,
    application_deadline,
    NULL,
    COALESCE(application_url, source_url, 'https://www.mida.gov.my'),
    now()
FROM grant_database
WHERE deadline_is_rolling = false
  AND application_deadline IS NOT NULL
ON CONFLICT (domain, deadline_name, due_date) DO NOTHING;

-- ── 3. Alert subscriptions (domain-wide, Pro-plan feature) ─────────────────
CREATE TABLE IF NOT EXISTS deadline_alert_subscriptions (
    id             uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id        uuid        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    domain         text        NOT NULL CHECK (
        domain IN (
            'government', 'education', 'legal', 'finance', 'healthcare',
            'epf', 'tax', 'business', 'immigration', 'culture'
        )
    ),
    created_at     timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id, domain)
);

CREATE INDEX IF NOT EXISTS deadline_alert_subscriptions_domain_idx
    ON deadline_alert_subscriptions (domain);

ALTER TABLE deadline_alert_subscriptions ENABLE ROW LEVEL SECURITY;

CREATE POLICY deadline_alert_subscriptions_owner
    ON deadline_alert_subscriptions FOR ALL
    TO authenticated
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

-- ── 4. Alert send ledger (dedup; service-role only, no client policies) ────
CREATE TABLE IF NOT EXISTS deadline_alert_sends (
    subscription_id     uuid NOT NULL REFERENCES deadline_alert_subscriptions(id) ON DELETE CASCADE,
    deadline_schedule_id uuid NOT NULL REFERENCES deadline_schedule(id) ON DELETE CASCADE,
    alert_day           int  NOT NULL,
    sent_at             timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (subscription_id, deadline_schedule_id, alert_day)
);

ALTER TABLE deadline_alert_sends ENABLE ROW LEVEL SECURITY;
-- No anon/authenticated policies: only the cron script, running as the
-- Supabase service role (bypasses RLS), ever reads or writes this table.
