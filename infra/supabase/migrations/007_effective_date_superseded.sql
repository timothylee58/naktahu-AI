-- 007_effective_date_superseded.sql
-- Add effective_date (when the rule/figure a chunk describes takes effect) and
-- superseded_by (explicit link to the chunk that replaces this one) to
-- document_chunks. These power the effective-date staleness check and the hard
-- rejection of superseded chunks in analyst_node — faithfulness/relevance can't
-- tell that a chunk is out of date, so this is tracked explicitly.

ALTER TABLE document_chunks
  ADD COLUMN IF NOT EXISTS effective_date date,
  ADD COLUMN IF NOT EXISTS superseded_by  uuid REFERENCES document_chunks (id) ON DELETE SET NULL;

-- Index for effective-date staleness scans.
CREATE INDEX IF NOT EXISTS document_chunks_effective_date
  ON document_chunks (effective_date)
  WHERE effective_date IS NOT NULL;

-- Partial index to quickly exclude superseded chunks.
CREATE INDEX IF NOT EXISTS document_chunks_superseded_by
  ON document_chunks (superseded_by)
  WHERE superseded_by IS NOT NULL;
