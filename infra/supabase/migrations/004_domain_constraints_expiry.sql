-- 004_domain_constraints_expiry.sql
-- Add domain check constraint, expiry_aware flag, and source_date column
-- to document_chunks for staleness detection in analyst_node.

ALTER TABLE document_chunks
  ADD CONSTRAINT valid_domain CHECK (
    domain IN ('tax', 'epf', 'business', 'education', 'healthcare', 'immigration')
  );

ALTER TABLE document_chunks
  ADD COLUMN IF NOT EXISTS expiry_aware boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS source_date  date;

-- Index for staleness queries: find expiry_aware chunks older than N days
CREATE INDEX IF NOT EXISTS document_chunks_expiry_staleness
  ON document_chunks (expiry_aware, source_date)
  WHERE expiry_aware = true;
