-- 055_grant_required_documents.sql
-- Adds the documents an applicant must prepare to grant_database, so the
-- Eligibility Agent can show "documents needed" next to each matched grant.
--
-- Shape: a JSON array of objects with any subset of name_en / name_bm / name_zh,
--   e.g. [{"name_en": "SSM business registration", "name_bm": "Pendaftaran perniagaan SSM",
--          "name_zh": "SSM 公司注册证明"}]
-- The backend validates and truncates each entry (analyst_node._normalise_documents)
-- and treats an empty array as "not yet listed" — it never reads empty as "no
-- documents needed".
--
-- This migration adds the column only. It deliberately seeds NO rows: required
-- documents are an agency's own published requirement, and an invented or
-- out-of-date list is worse than an honest "not yet listed". Fill rows from each
-- programme's official application guide.
--
-- No RLS change: grant_database already has its policies, and adding a column
-- does not alter them. Backend code works before this is applied (select("*")
-- simply returns no such key, which normalises to an empty list).

ALTER TABLE grant_database
  ADD COLUMN IF NOT EXISTS required_documents jsonb NOT NULL DEFAULT '[]'::jsonb
    CHECK (jsonb_typeof(required_documents) = 'array');

COMMENT ON COLUMN grant_database.required_documents IS
  'Array of {name_en,name_bm,name_zh} objects: documents the applicant must prepare. Empty = not yet listed.';
