-- 062: remove duplicate grant_database rows and stop them recurring.
--
-- WHAT: a read-only audit found 'Cradle Elevate' stored 3 times. Migration 050 INSERTed it
-- with no conflict guard and was evidently pasted into the SQL editor more than once. The
-- duplicates show up as repeated cards in Grant Finder and make the draft generator's
-- programme lookup depend on which copy the database returns first.
--
-- WHAT IT DOES: keeps the OLDEST row per (lower(programme_name), agency), deletes the rest,
-- then adds a unique index on that pair so a re-run of any seed migration cannot duplicate
-- a programme again. Idempotent. Nothing else in grant_database is touched.
-- (deadline_schedule has no foreign key to grant_database, per migration 023.)
--
-- Paste into the Supabase SQL editor. Step 1 previews the rows that will go; run it first.

-- 1. Preview: rows that will be deleted (everything but the oldest per programme+agency).
SELECT id, programme_name, agency, created_at
FROM (
  SELECT id, programme_name, agency, created_at,
         row_number() OVER (PARTITION BY lower(programme_name), lower(agency)
                            ORDER BY created_at, id) AS rn
  FROM grant_database
) d
WHERE rn > 1;

-- 2. Delete them.
DELETE FROM grant_database
WHERE id IN (
  SELECT id FROM (
    SELECT id,
           row_number() OVER (PARTITION BY lower(programme_name), lower(agency)
                              ORDER BY created_at, id) AS rn
    FROM grant_database
  ) d
  WHERE rn > 1
);

-- 3. Prevent recurrence.
CREATE UNIQUE INDEX IF NOT EXISTS uq_grant_database_programme_agency
  ON grant_database (lower(programme_name), lower(agency));
