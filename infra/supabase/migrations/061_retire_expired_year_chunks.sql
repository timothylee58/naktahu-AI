-- 061_retire_expired_year_chunks.sql
-- Remove the past-year chunks of the two LHDN per-year pages, so the current year is retrievable.
-- Data-only: no schema change and nothing in the API depends on it, so the API keeps working
-- whether or not it has been applied.
--
-- Why
--   https://www.hasil.gov.my/en/individu/pelepasan-cukai/  (tax reliefs: 11 yearly tables) and
--   https://www.hasil.gov.my/en/individu/kadar-cukai/      (individual rates: YA2023 to YA2025)
--   were ingested with one chunk group per year of assessment. analyst_node drops an expired chunk
--   (effective_until in the past), but only AFTER retrieval: the near-identical past-year tables
--   fill the top-5 slots and push the one current table out. A live tax eval (2026-11-16) showed
--   it: child-relief ended with "no usable chunks" (confidence 0.00), and questions that passed
--   before fell back to "the context does not contain it". The ingester now keeps only the current
--   year (extractor lhdn_accordion_current); this deletes the past-year rows already stored.
--
-- Safe by construction
--   * It deletes only rows from those two URLs whose effective_until is set AND already past.
--   * The DO block refuses to run unless each URL still has at least one CURRENT chunk
--     (effective_until IS NULL), so a page can never be left with nothing.
--   * Idempotent: re-running deletes nothing further. A row that another row points at via
--     superseded_by would make the DELETE fail on the foreign key, not orphan anything.
--   * Reversible: re-running the Ingest Sources workflow for these sources re-creates the rows
--     only if the extractor allows it; the past years are intentionally not re-ingested.
--
-- Paste this file into the Supabase SQL editor. Read the preview SELECT first.

-- PREVIEW: what would go (expect ~49 reliefs rows for YA2015-YA2024 and the older rate years).
SELECT source_url, source_title, effective_date, effective_until
FROM document_chunks
WHERE source_url IN (
        'https://www.hasil.gov.my/en/individu/pelepasan-cukai/',
        'https://www.hasil.gov.my/en/individu/kadar-cukai/'
      )
  AND effective_until IS NOT NULL
  AND effective_until < CURRENT_DATE
ORDER BY source_url, effective_date;

DO $$
DECLARE
    missing text;
BEGIN
    SELECT string_agg(u, ', ') INTO missing
    FROM unnest(ARRAY[
        'https://www.hasil.gov.my/en/individu/pelepasan-cukai/',
        'https://www.hasil.gov.my/en/individu/kadar-cukai/'
    ]) AS u
    WHERE NOT EXISTS (
        SELECT 1 FROM document_chunks d
        WHERE d.source_url = u AND d.effective_until IS NULL
    );
    IF missing IS NOT NULL THEN
        RAISE EXCEPTION 'Refusing to run: no current chunk for %', missing;
    END IF;

    DELETE FROM document_chunks
    WHERE source_url IN (
            'https://www.hasil.gov.my/en/individu/pelepasan-cukai/',
            'https://www.hasil.gov.my/en/individu/kadar-cukai/'
          )
      AND effective_until IS NOT NULL
      AND effective_until < CURRENT_DATE;
END
$$;

-- VERIFY: only current rows should remain for the two pages.
SELECT source_url, count(*) AS rows_left,
       count(*) FILTER (WHERE effective_until IS NOT NULL) AS expired_left
FROM document_chunks
WHERE source_url IN (
        'https://www.hasil.gov.my/en/individu/pelepasan-cukai/',
        'https://www.hasil.gov.my/en/individu/kadar-cukai/'
      )
GROUP BY source_url;
