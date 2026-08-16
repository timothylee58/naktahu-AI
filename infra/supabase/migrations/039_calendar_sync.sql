-- 039_calendar_sync.sql
-- Two-way OAuth calendar sync for Deadline Monitor (Google Calendar +
-- Microsoft Calendar). "Two-way" here means NakTahu creates/updates/deletes
-- calendar EVENTS on the user's behalf as their subscribed deadlines change
-- — it does NOT read the user's existing calendar. Scoped deliberately
-- narrow: Google's calendar.events scope is write-capable but not full
-- calendar read; Microsoft Graph has no write-only equivalent to that (the
-- narrowest write-capable Graph scope, Calendars.ReadWrite, is technically
-- read+write) — noted honestly in app/services/calendar_sync.py rather than
-- claimed as narrower than it is.
--
-- Corresponding Python/frontend changes (same PR):
--   - apps/api/core/config.py                    google/microsoft OAuth + encryption key settings
--   - apps/api/app/services/token_encryption.py   Fernet encrypt/decrypt for refresh tokens at rest
--   - apps/api/services/calendar_sync.py          OAuth flow + calendar push/update/delete
--   - apps/api/routers/calendar.py                connect/callback/status/disconnect endpoints
--   - apps/api/scripts/agents/deadline_monitor.py sync step alongside the existing email dispatch
--   - apps/web/src/app/agents/deadline-monitor/page.tsx  connect-card UI
--   - apps/web/src/lib/i18n/index.tsx             calendar.* keys
--
-- Both tables hold per-user data that must never be readable by another
-- user even through a bug — explicit user-scoped RLS policies on both,
-- unlike madani_scheme (037)/grant_database (020)'s public-readable
-- catalogues. All backend access still goes through the service-role
-- client (matching every other table in this app), which bypasses RLS —
-- these policies are the safety net for any future direct-from-client read.

CREATE TABLE IF NOT EXISTS calendar_connections (
    id                      uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                 uuid        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    provider                text        NOT NULL CHECK (provider IN ('google', 'microsoft')),
    -- Fernet-encrypted refresh token (app/services/token_encryption.py) — the
    -- only long-lived secret stored. Access tokens are never persisted: a
    -- fresh one is exchanged from the refresh token immediately before each
    -- push run, which avoids a second at-rest secret and any "is this cached
    -- access token still valid" staleness bug.
    encrypted_refresh_token text        NOT NULL,
    scope                   text        NOT NULL,
    -- Which calendar to write events into. 'primary' for both providers'
    -- default calendar; a future settings UI could let a user pick another.
    calendar_id             text        NOT NULL DEFAULT 'primary',
    connected_at            timestamptz NOT NULL DEFAULT now(),
    last_synced_at          timestamptz,
    -- Set on a failed push (e.g. token revoked by the user at the provider
    -- side) and cleared on the next success — surfaced via GET
    -- /api/v1/calendar/status so the UI can prompt "reconnect needed"
    -- instead of silently retrying a dead connection forever.
    last_error              text,
    UNIQUE (user_id, provider)
);

CREATE INDEX IF NOT EXISTS idx_calendar_connections_user ON calendar_connections(user_id);

ALTER TABLE calendar_connections ENABLE ROW LEVEL SECURITY;
CREATE POLICY "calendar_connections_owner_select"
  ON calendar_connections FOR SELECT
  TO authenticated
  USING (auth.uid() = user_id);
CREATE POLICY "calendar_connections_owner_delete"
  ON calendar_connections FOR DELETE
  TO authenticated
  USING (auth.uid() = user_id);

-- Maps one deadline_schedule row -> one external calendar event per
-- (user, provider), so a due-date drift (deadline_monitor.py already
-- detects and corrects these via its scraped-date-vs-stored-date diff)
-- updates the SAME calendar event instead of creating a duplicate.
CREATE TABLE IF NOT EXISTS calendar_event_links (
    id                      uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                 uuid        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    provider                text        NOT NULL CHECK (provider IN ('google', 'microsoft')),
    deadline_schedule_id    uuid        NOT NULL REFERENCES deadline_schedule(id) ON DELETE CASCADE,
    external_event_id       text        NOT NULL,
    last_pushed_due_date    date        NOT NULL,
    created_at              timestamptz NOT NULL DEFAULT now(),
    updated_at              timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id, provider, deadline_schedule_id)
);

CREATE INDEX IF NOT EXISTS idx_calendar_event_links_user ON calendar_event_links(user_id);

ALTER TABLE calendar_event_links ENABLE ROW LEVEL SECURITY;
CREATE POLICY "calendar_event_links_owner_select"
  ON calendar_event_links FOR SELECT
  TO authenticated
  USING (auth.uid() = user_id);
