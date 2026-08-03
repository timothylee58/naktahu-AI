-- 028_history_full_response.sql
-- Query history previously only stored a 150-char response_summary, so
-- clicking a history entry could only re-prompt the LLM (a fresh, possibly
-- different answer) instead of showing back what the user actually saw.
-- Add the full response text plus confidence/suggestions/agency_contact so
-- the frontend can reconstruct the exact original chat turn without a new
-- query. response_summary is kept as-is for the sidebar/list preview.

ALTER TABLE user_sessions
    ADD COLUMN IF NOT EXISTS response_text   text,
    ADD COLUMN IF NOT EXISTS confidence      real,
    ADD COLUMN IF NOT EXISTS suggestions     jsonb NOT NULL DEFAULT '[]',
    ADD COLUMN IF NOT EXISTS agency_contact  jsonb;
