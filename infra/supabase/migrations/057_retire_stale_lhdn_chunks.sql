-- 057_retire_stale_lhdn_chunks.sql
-- Remove the document_chunks rows that the LHDN accordion extractor replaces.
-- Data-only: no schema change and nothing in the API depends on it, so the API
-- keeps working whether or not it has been applied.
--
-- Why
--   1. Three rows from the FIRST `lhdn-company-tax-rates` ingest are junk: the
--      generic HTML extractor stored a navigation menu, a rate table stripped of
--      its figures (labels with "(24%)", "(25%)", "(26%)", "(27%)" and none of the
--      SME tiers), and the site disclaimer. The middle one is also mis-dated
--      (effective_date 2025-01-01, taken from a menu link). They carry only a
--      bge-m3 vector, so no user can retrieve them today, but once
--      EMBEDDING_PROFILE=ilmu_bge_m3 they would be searchable and could be quoted.
--   2. Nine rows hand-written on 2026-05-26 cite
--      https://www.hasil.gov.my/en/individual/individual-life-cycle/how-to-declare-income/tax-rate/
--      as their source. That URL returns 404 (check_sources, 2026-10-14) and the
--      text was never extracted from it, so every answer built on them shows a
--      citation chip that goes nowhere.
--
-- Order matters. Apply PART 1 any time. Apply PART 2 only AFTER the live site can
-- retrieve the new LHDN chunks, i.e. after EMBEDDING_PROFILE is switched to
-- ilmu_bge_m3 on Railway (the new chunks have only a bge-m3 vector), otherwise the
-- site is left with no individual income tax rates at all. PART 2 refuses to run
-- if the new chunks are missing. PART 3 is optional and commented out.
--
-- Idempotent: re-running deletes nothing further. Rows that other rows point at
-- via superseded_by, and supersede_candidates rows, cascade or block the delete;
-- none reference these rows (checked 2026-10-14).
--
-- Paste this file into the Supabase SQL editor. Read the preview SELECTs first.

-- ── PART 1: the three junk rows from the first lhdn-company-tax-rates ingest ─────
-- Preview: expect 3 rows titled 'Kadar Cukai Syarikat', created 2026-10-14 05:52 UTC.
SELECT id, source_title, created_at, left(regexp_replace(content, '\s+', ' ', 'g'), 80) AS start
FROM document_chunks
WHERE id IN (
    '300ef766-ef03-4ab2-8e24-bc46232530ae',
    '4e7e04ba-e4a8-41e0-a493-e0190f373246',
    '888ed200-b8a8-4895-b643-c4da0b15cbfe'
);

DELETE FROM document_chunks
WHERE id IN (
    '300ef766-ef03-4ab2-8e24-bc46232530ae',
    '4e7e04ba-e4a8-41e0-a493-e0190f373246',
    '888ed200-b8a8-4895-b643-c4da0b15cbfe'
)
  AND source_url = 'https://www.hasil.gov.my/en/syarikat/kadar-cukai-syarikat/'
  AND embedding IS NULL;

-- ── PART 2: the hand-written YA2023 rate schedule (apply after the cutover) ───────
-- The new chunks "Individual Income Tax Rates (LHDN) - Year of Assessment 2023, 2024 & 2025"
-- hold the same bands extracted from LHDN's own page. Preview: expect 1 row.
SELECT id, source_title, source_url, left(regexp_replace(content, '\s+', ' ', 'g'), 80) AS start
FROM document_chunks
WHERE id = '28ebd8bd-22bf-4562-9c49-05b4725703a4';

DO $$
BEGIN
    IF (SELECT count(*) FROM document_chunks
        WHERE source_title LIKE 'Individual Income Tax Rates (LHDN) — Year of Assessment 2023, 2024 & 2025%'
          AND embedding_v2 IS NOT NULL) < 1 THEN
        RAISE EXCEPTION 'the new LHDN individual-rates chunks are missing; not retiring the old rate schedule';
    END IF;

    DELETE FROM document_chunks
    WHERE id = '28ebd8bd-22bf-4562-9c49-05b4725703a4'
      AND source_url = 'https://www.hasil.gov.my/en/individual/individual-life-cycle/how-to-declare-income/tax-rate/';
END $$;

-- ── PART 3 (optional, commented out): the other eight hand-written chunks ────────
-- They cite the same dead URL but hold facts the new LHDN ingest does NOT replace:
-- personal reliefs (RM9,000 self, RM4,000 spouse, ...), Form BE / Form B deadlines,
-- e-Filing registration, RPGT, stamp duty on property transfer, SST and PCB/MTD.
-- Deleting them removes those facts from answers (and the tax accuracy eval key
-- expects several of them). Uncomment only once replacements are ingested, or if a
-- missing answer is preferred to one whose citation is a dead link.
--
-- DELETE FROM document_chunks
-- WHERE id IN (
--     'b6b5705b-6dfd-4331-8c17-01ae680caa0b',  -- Personal Tax Relief YA2023
--     '79938c90-86de-4bfb-bce7-2ebb16fe8639',  -- Tax Return Forms
--     '89499d20-65b5-4828-9735-6683a29ec347',  -- e-Filing Deadlines
--     'bcd25802-6722-49f2-ae4e-1468619a6ce2',  -- e-Filing Registration Guide
--     '6a86d0b8-a891-4311-9c4b-a8639846bfc6',  -- Real Property Gains Tax (RPGT)
--     'fea80878-985c-4a23-a4b9-752559cb809d',  -- Stamp Duty on Property Transfer
--     'a7ae079a-0aac-4295-bcba-ecc72017a4c7',  -- Sales and Service Tax (SST)
--     'e1484cf4-5dd7-4a99-83a8-849cb4b33e5f'   -- Monthly Tax Deduction (PCB/MTD)
-- )
--   AND source_url = 'https://www.hasil.gov.my/en/individual/individual-life-cycle/how-to-declare-income/tax-rate/';

-- ── Verification (run after PART 1; and again after PART 2) ──────────────────────
-- After PART 1: 0 rows with title 'Kadar Cukai Syarikat'. After PART 2: 0 rows for
-- the id 28ebd8bd-..., and the new 'Individual Income Tax Rates (LHDN) ...' rows remain.
SELECT
    count(*) FILTER (WHERE source_title = 'Kadar Cukai Syarikat')                          AS junk_company_rows_left,
    count(*) FILTER (WHERE id = '28ebd8bd-22bf-4562-9c49-05b4725703a4')                    AS old_rate_schedule_left,
    count(*) FILTER (WHERE source_title LIKE 'Individual Income Tax Rates (LHDN)%')        AS new_individual_chunks,
    count(*) FILTER (WHERE source_url LIKE '%how-to-declare-income/tax-rate%')             AS rows_citing_the_dead_url
FROM document_chunks;
