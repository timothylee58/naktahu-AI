-- 016_widen_domain_constraint.sql
-- document_chunks.valid_domain (004_domain_constraints_expiry.sql) only
-- allowed 6 domains, but router_node/guard_node's _VALID_DOMAINS have
-- included 10 since the guard/router hardening work — 'government' (the
-- router's own default fallback domain), 'legal', 'finance', and 'culture'
-- were never added here. Any ingestion or insert targeting one of those
-- four domains has been silently rejected by the DB ever since.

ALTER TABLE document_chunks DROP CONSTRAINT IF EXISTS valid_domain;

ALTER TABLE document_chunks
  ADD CONSTRAINT valid_domain CHECK (
    domain IN (
        'government', 'education', 'legal', 'finance', 'healthcare',
        'epf', 'tax', 'business', 'immigration', 'culture'
    )
  );
