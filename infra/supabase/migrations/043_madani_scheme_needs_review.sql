-- 043_madani_scheme_needs_review.sql
-- Adds a review gate to madani_scheme, separate from is_active.
--
-- is_active (migration 037) means "still listed on ihsanmadani.gov.my as
-- of the last scrape" — it says nothing about whether eligibility_rules is
-- trustworthy. needs_review means "eligibility_rules has not yet been
-- confirmed as either (a) a real extracted constraint, or (b) a
-- human-confirmed 'genuinely open to all' — as opposed to an empty {}
-- that could just as easily mean 'the LLM extraction failed to find
-- anything'." These are orthogonal: a scheme can be active but unreviewed
-- (freshly scraped, not yet confirmed), or reviewed but later delisted
-- (is_active flips false, needs_review stays false — the rules are still
-- trusted, the scheme just isn't offered any more).
--
-- Defaults to true (every row starts unreviewed) so a bulk INSERT from
-- scripts/ingest_madani.py can never accidentally land as "confirmed
-- correct" without deliberately setting the column.
--
-- match_node.py filters needs_review=false rows only (see its own updated
-- comment) — an eligibility_rules row nobody has confirmed must never be
-- surfaced as "you qualify", because migration 037's own filter treats an
-- absent constraint key as "no restriction", i.e. matches everyone. An
-- unreviewed {} is therefore indistinguishable from "confirmed open to
-- all" unless this column exists to tell them apart.
ALTER TABLE madani_scheme ADD COLUMN IF NOT EXISTS needs_review boolean NOT NULL DEFAULT true;

CREATE INDEX IF NOT EXISTS idx_madani_scheme_needs_review ON madani_scheme(needs_review) WHERE is_active;
