-- 053_supersede_review_queue.sql
-- Review queue for "this new chunk probably replaces that old one".
--
-- When ingest_feed.py inserts a chunk in a time-sensitive domain (tax, epf,
-- immigration) it looks for older, very similar chunks in the same domain and
-- records each pair here as 'pending'. Nothing is retired automatically: a
-- wrong automatic supersede silently hides a rule that is still in force,
-- which is worse than a short delay while a human checks the pair.
--
-- review_supersede.py lists pending pairs and calls approve_supersede() or
-- reject_supersede(). Approval is date-aware (see the function below), which
-- is what keeps the November scenario correct: a rule announced in November
-- that starts 1 Jan closes the old rule's window on 31 Dec instead of
-- retiring it today.
--
-- Access: service role only. RLS is enabled with no policies for anon or
-- authenticated, so the API's user-facing clients can neither read nor write
-- it; the service role (ingestion and review scripts) bypasses RLS.
-- Requires migration 052 (effective_until column).

CREATE TABLE IF NOT EXISTS supersede_candidates (
    id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    new_chunk_id  uuid        NOT NULL REFERENCES document_chunks(id) ON DELETE CASCADE,
    old_chunk_id  uuid        NOT NULL REFERENCES document_chunks(id) ON DELETE CASCADE,
    similarity    float       NOT NULL,
    status        text        NOT NULL DEFAULT 'pending'
                              CHECK (status IN ('pending', 'approved', 'rejected')),
    created_at    timestamptz NOT NULL DEFAULT now(),
    reviewed_at   timestamptz,
    CONSTRAINT supersede_candidates_distinct CHECK (new_chunk_id <> old_chunk_id),
    CONSTRAINT supersede_candidates_pair_unique UNIQUE (new_chunk_id, old_chunk_id)
);

CREATE INDEX IF NOT EXISTS supersede_candidates_pending_idx
    ON supersede_candidates (created_at) WHERE status = 'pending';

ALTER TABLE supersede_candidates ENABLE ROW LEVEL SECURITY;

-- Approve one pending pair, atomically.
--   New rule already in force (no start date, or start <= today):
--       old.superseded_by = new  -> analyst_node hard-rejects the old chunk.
--   New rule starts in the future:
--       old.effective_until = new.effective_date - 1 day  -> the old rule
--       stays the current answer until then, and the new one is surfaced as
--       a pending change; at the boundary the old window closes by itself.
-- An existing earlier effective_until on the old chunk is never extended.
CREATE OR REPLACE FUNCTION approve_supersede(candidate_id uuid)
RETURNS text
LANGUAGE plpgsql
AS $$
DECLARE
    cand      supersede_candidates%ROWTYPE;
    new_start date;
    outcome   text;
BEGIN
    SELECT * INTO cand FROM supersede_candidates WHERE id = candidate_id FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'supersede candidate % not found', candidate_id;
    END IF;
    IF cand.status <> 'pending' THEN
        RAISE EXCEPTION 'supersede candidate % is already %', candidate_id, cand.status;
    END IF;

    SELECT effective_date INTO new_start FROM document_chunks WHERE id = cand.new_chunk_id;

    IF new_start IS NOT NULL AND new_start > current_date THEN
        UPDATE document_chunks
           SET effective_until = LEAST(COALESCE(effective_until, new_start - 1), new_start - 1)
         WHERE id = cand.old_chunk_id;
        outcome := 'window_closed';
    ELSE
        UPDATE document_chunks
           SET superseded_by = cand.new_chunk_id
         WHERE id = cand.old_chunk_id;
        outcome := 'superseded';
    END IF;

    UPDATE supersede_candidates
       SET status = 'approved', reviewed_at = now()
     WHERE id = candidate_id;
    RETURN outcome;
END;
$$;

CREATE OR REPLACE FUNCTION reject_supersede(candidate_id uuid)
RETURNS void
LANGUAGE sql
AS $$
    UPDATE supersede_candidates
       SET status = 'rejected', reviewed_at = now()
     WHERE id = candidate_id AND status = 'pending';
$$;

-- Functions are callable by PUBLIC by default; restrict to the service role.
REVOKE EXECUTE ON FUNCTION approve_supersede(uuid) FROM PUBLIC, anon, authenticated;
REVOKE EXECUTE ON FUNCTION reject_supersede(uuid)  FROM PUBLIC, anon, authenticated;
