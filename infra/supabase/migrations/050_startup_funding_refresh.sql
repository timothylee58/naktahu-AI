-- Refresh grant_database with the startup funding landscape as it stood in
-- September 2026 (CLAUDE.md Trap #5: this file is not auto-applied — paste
-- it into the Supabase SQL editor).
--
-- Sourcing note, same caveat as scripts/sources.py's WebSearch-found
-- entries: this environment's network egress proxy blocks direct fetches to
-- .gov.my and most Malaysian GLC domains (cradle.com.my, mdec.my, mosti.gov.my
-- all confirmed blocked again this session), so nothing here was verified by
-- a direct fetch. Every figure below is corroborated by at least one
-- independent WebSearch result (a news report, an official press-release
-- PDF snippet, or the programme's own page surfaced in search) — not
-- invented, not extrapolated from an unrelated figure. Where a programme's
-- actual per-company amount could not be corroborated (e.g. MOSTI's BIG 2.0
-- corporate-innovation fund, RM15M total allocation but no confirmed
-- per-recipient figure), it is deliberately NOT added as a grant_database
-- row — see scripts/sources.py's own rule against a plausible-looking guess
-- on a page whose job is real citations. BIG 2.0 is covered instead as a
-- RAG source below (migration only adds the row; the Source registration is
-- a separate, code-reviewed change to scripts/sources.py).
--
-- 1. New row: Cradle Elevate (launched Apr 2026, not in the original
--    Budget-2026 seed from migration 020 — that seed predates the launch).
-- 2. last_verified bumped ONLY on the three existing rows this session's
--    WebSearch actually corroborated against current reporting (CIP Sprint,
--    MDAG, MSME Digital Grant MADANI) — the other seven rows are left
--    untouched rather than bumping a date with no real evidence behind it.

-- ── 1. Cradle Elevate — bridging equity investment, Pre-Series A to Series A ─
-- RM10M total allocation, RM500k-2M per company (TheEdgeMalaysia, The Star,
-- TechNode Global, MOSTI's own press release all corroborate the RM10M/
-- RM500k-2M figures). Equity, not a grant in the fixed-amount-band sense of
-- CIP Spark/Sprint — grant_type 'equity' already exists as a value in this
-- table (used nowhere yet; this is the first equity-type row). No fixed
-- application deadline was reported — intake is by expression of interest
-- (elevate@cradle.com.my), so deadline_is_rolling = true rather than a
-- guessed date.
INSERT INTO grant_database (
  programme_name, agency, grant_type,
  amount_min_myr, amount_max_myr,
  eligible_sectors, bumiputera_required,
  company_age_min_months, deadline_is_rolling,
  application_url, processing_weeks_min, processing_weeks_max,
  budget_year, stackable_with, conflicts_with,
  source_url, last_verified, notes_en
) VALUES (
  'Cradle Elevate', 'Cradle Fund', 'equity',
  500000, 2000000,
  ARRAY['all'], false,
  NULL, true,
  'https://cradle.com.my/elevate.html',
  NULL, NULL, 2026,
  ARRAY[]::text[],
  ARRAY['CIP Sprint'],
  'https://www.mosti.gov.my/en/siaran-kenyataan-media/cradle-lancar-elevate-bernilai-rm10-juta-dan-startup-accelerator-programme-pacu-pertumbuhan-peringkat-awal',
  '2026-09-19',
  'Bridging equity investment for startups that have passed seed stage but '
  || 'not yet reached Series A — closes the pre-Series-A funding gap, not a '
  || 'grant. RM10M total allocation across the programme. Launched alongside '
  || 'the Cradle Startup Accelerator Programme 2026. Apply by expression of '
  || 'interest to elevate@cradle.com.my or via the MYStartup portal '
  || '(mystartup.gov.my) — no fixed application window. Marked as '
  || 'conflicting with CIP Sprint since both target overlapping growth-stage '
  || 'funding gaps under the same agency; not independently confirmed as '
  || 'formally incompatible, flagged here for a human to verify before the '
  || 'eligibility agent treats it as a hard exclusion.'
);

-- ── 2. Re-verification bump — only the three rows this session's WebSearch
--    actually corroborated, each against an independent source from the
--    original migration 020 seed:
--    - CIP Sprint: "up to RM600,000... eighteen months" confirmed via
--      SuperCFO's 2026 founder guide, matches the RM300k-600k/6-12mo row.
--    - MDAG: "RM53 million allocation Budget 2026" confirmed via
--      FundingSocieties' Budget 2026 summary, matches exactly.
--    - MSME Digital Grant MADANI: "RM150 million... 50,000 SMEs" confirmed
--      via the same summary, matches exactly (MDEC's own programme is
--      publicly branded "GoDigital MADANI" now — notes_en left as-is since
--      the underlying figures are unchanged, not a rename that affects
--      matching logic).
UPDATE grant_database
   SET last_verified = '2026-09-19'
 WHERE programme_name = 'CIP Sprint' AND agency = 'Cradle Fund';

UPDATE grant_database
   SET last_verified = '2026-09-19'
 WHERE programme_name = 'Malaysia Digital Acceleration Grant (MDAG)' AND agency = 'MDEC';

UPDATE grant_database
   SET last_verified = '2026-09-19'
 WHERE programme_name = 'MSME Digital Grant MADANI' AND agency = 'MDEC';
