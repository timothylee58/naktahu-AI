-- Screenshot attachments for feedback + a 'flagged' triage state.
--
-- Users reporting a wrong answer (thumbs-down in chat) or a bug (profile
-- feedback card) can now attach one image. The backend re-encodes every
-- upload (strips EXIF, rejects anything Pillow cannot decode) and writes it
-- to a PRIVATE bucket with the service-role key; this migration only adds
-- the bucket and the columns that point at it.
--
-- 'flagged' = the feedback verifier (services/feedback_guard.py) found it
-- suspicious (link spam, gibberish) but not clearly hostile. Flagged rows are
-- stored for a human to look at and are never surfaced to the mining
-- pipeline. Outright prompt-injection / markup is rejected before insert.

INSERT INTO storage.buckets (id, name, public)
VALUES ('feedback-attachments', 'feedback-attachments', false)
ON CONFLICT (id) DO NOTHING;
-- No storage.objects policies on purpose: with RLS on and no policy, anon and
-- authenticated users cannot read or write this bucket; only the backend's
-- service-role client can.

ALTER TABLE product_feedback ADD COLUMN IF NOT EXISTS attachment_path text;

ALTER TABLE product_feedback DROP CONSTRAINT IF EXISTS product_feedback_status_check;
ALTER TABLE product_feedback ADD CONSTRAINT product_feedback_status_check
  CHECK (status IN ('new', 'reviewing', 'planned', 'done', 'declined', 'flagged'));

ALTER TABLE feedback ADD COLUMN IF NOT EXISTS attachment_path text;
ALTER TABLE feedback ADD COLUMN IF NOT EXISTS user_comment text;
