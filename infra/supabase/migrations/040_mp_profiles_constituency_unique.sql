-- 040_mp_profiles_constituency_unique.sql
--
-- Adds a UNIQUE constraint on mp_profiles.constituency_code so
-- scripts/ingest_parliament/seed_mp_profiles.py's upsert(on_conflict=
-- "constituency_code") is actually idempotent, instead of erroring or
-- (with plain insert) duplicating a row every time the roster is re-seeded
-- after an election/by-election. Migration 025 created mp_profiles without
-- this constraint — the seeding pipeline that needed it didn't exist yet.
--
-- Nothing else in this migration: RLS/policies for mp_profiles already
-- exist from 025 and are unaffected by adding a constraint to an existing
-- column.

ALTER TABLE mp_profiles
  ADD CONSTRAINT mp_profiles_constituency_code_key UNIQUE (constituency_code);
