-- 025_parliament_watch.sql
-- New product vertical: Parliament Watch (MP profiles, voting records,
-- constituency lookup). This migration ships SCHEMA + STRUCTURED LOOKUPS
-- ONLY — no Hansard content is ingested by this PR. Hansard PDF ingestion
-- (populating document_chunks with domain='hansard' content and building
-- the ingestion pipeline) is explicitly deferred to a follow-up PR.
--
-- Corrections made to the originally pasted SQL before this file was
-- written (both required for the statements below it to resolve):
--   1. Added `parliament_bills` (bill_number, title_en/bm, status,
--      sponsoring_ministry, parliament_no, session_no, tabled_date,
--      passed_date, source_url) so `mp_votes.bill_id`'s FK reference has
--      a table to point at.
--   2. Added `document_chunks.clause_reference` (via ALTER TABLE ADD
--      COLUMN IF NOT EXISTS) so the `hansard_segments` view's
--      `dc.clause_reference` reference resolves. clause_reference
--      generalises beyond Hansard (any ingested source with an internal
--      pinpoint reference — Hansard page, gazette clause, bill section)
--      so it lives on document_chunks itself, not a Hansard-only table.
--
-- Domain-list decision (Trap #6, migration 016's canonical 10-domain
-- list: government, education, legal, finance, healthcare, epf, tax,
-- business, immigration, culture):
--   'hansard' is deliberately NOT added as an 11th canonical domain in
--   this PR. This PR ships zero ingested content — there is nothing to
--   tag with any domain yet — so widening router_node/guard_node's
--   _VALID_DOMAINS, ingest_feed.py's copy, and the valid_domain CHECK
--   constraint now would be speculative and would touch the shared
--   domain-classification surface (which the router uses for every
--   query, not just Parliament Watch) ahead of any actual need. The
--   safe failure mode is left in place on purpose: an insert attempting
--   domain='hansard' against document_chunks today is correctly
--   REJECTED by the existing (016) CHECK constraint, and the
--   hansard_segments view below simply returns zero rows until a
--   follow-up PR (a) builds the Hansard ingestion pipeline and (b)
--   widens the domain list at all three sites Trap #6 requires,
--   together with a new migration, in the same change.

-- ── 1. Parliament sessions (Dewan Rakyat terms) ────────────────────────────
CREATE TABLE IF NOT EXISTS parliament_sessions (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  parliament_no   smallint NOT NULL,        -- e.g. 15 (15th Parliament)
  session_no      smallint NOT NULL,        -- session within parliament
  start_date      date,
  end_date        date,
  is_current      boolean DEFAULT false,
  total_sittings  smallint DEFAULT 0,
  UNIQUE(parliament_no, session_no)
);

-- ── 2. MP profiles ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS mp_profiles (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Identity
  full_name           text NOT NULL,
  full_name_bm        text,               -- Bahasa Malaysia name if different
  ic_name             text,               -- name as on IC
  salutation          text,               -- YB, YAB, Dato', Tan Sri

  -- Constituency
  constituency_code   text NOT NULL,      -- e.g. "P130" (Parliament) or "N.28" (ADUN)
  constituency_name   text NOT NULL,      -- e.g. "Rasah"
  constituency_type   varchar(16) DEFAULT 'parliament', -- parliament | adun
  state               text,              -- e.g. "Negeri Sembilan"

  -- Party & coalition
  party               text,              -- DAP, PKR, UMNO, BERSATU, etc.
  coalition           text,              -- Pakatan Harapan, Perikatan Nasional, etc.
  is_cabinet_minister boolean DEFAULT false,
  ministry            text,              -- if minister
  cabinet_role        text,              -- e.g. "Minister of Finance"

  -- Term info
  parliament_no       smallint,
  elected_date        date,
  by_election         boolean DEFAULT false,
  is_active           boolean DEFAULT true,

  -- Metadata
  gender              varchar(8),         -- male | female
  date_of_birth       date,
  hometown            text,
  education           text,
  occupation_pre_mp   text,
  profile_image_url   text,
  mymp_id             text,               -- MyMP.org.my ID for cross-reference
  parlimen_url        text,               -- parlimen.gov.my profile URL

  -- Computed scores (updated by nightly cron)
  attendance_rate     float,             -- sessions attended / total sessions
  questions_count     int DEFAULT 0,     -- total parliamentary questions
  motions_count       int DEFAULT 0,     -- total motions tabled
  bills_sponsored     int DEFAULT 0,     -- bills tabled as primary sponsor
  last_score_updated  timestamptz,

  created_at          timestamptz DEFAULT now(),
  updated_at          timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_mp_constituency
  ON mp_profiles(constituency_code);
CREATE INDEX IF NOT EXISTS idx_mp_party
  ON mp_profiles(party);
CREATE INDEX IF NOT EXISTS idx_mp_state
  ON mp_profiles(state);
CREATE INDEX IF NOT EXISTS idx_mp_parliament
  ON mp_profiles(parliament_no);
CREATE INDEX IF NOT EXISTS idx_mp_fts
  ON mp_profiles USING gin(
    to_tsvector('english',
      coalesce(full_name,'') || ' ' ||
      coalesce(constituency_name,'') || ' ' ||
      coalesce(party,'') || ' ' ||
      coalesce(state,'')
    )
  );

-- ── 3. Parliament bills registry ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS parliament_bills (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  bill_number       text UNIQUE NOT NULL,  -- e.g. "D.R. 15/2026"
  title_en          text,
  title_bm          text,
  status            varchar(32),           -- tabled | first_reading | second_reading | third_reading | passed | withdrawn
  sponsoring_ministry text,
  parliament_no     smallint,
  session_no        smallint,
  tabled_date       date,
  passed_date       date,
  source_url        text,
  created_at        timestamptz DEFAULT now(),
  updated_at        timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_bills_number ON parliament_bills(bill_number);
CREATE INDEX IF NOT EXISTS idx_bills_status ON parliament_bills(status);

-- ── 4. MP voting records ───────────────────────────────────────────────────
-- One row per MP per bill per reading stage
CREATE TABLE IF NOT EXISTS mp_votes (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  mp_id             uuid NOT NULL REFERENCES mp_profiles(id) ON DELETE CASCADE,
  bill_id           uuid REFERENCES parliament_bills(id) ON DELETE SET NULL,

  -- Vote detail
  bill_number       text,                -- denormalised for query speed
  bill_title_en     text,
  bill_title_bm     text,
  reading_stage     varchar(32),         -- second_reading | third_reading | committee_vote
  vote              varchar(16) NOT NULL, -- for | against | absent | abstain
  vote_date         date NOT NULL,
  sitting_id        text,                -- Hansard sitting reference

  -- Context
  parliament_no     smallint,
  session_no        smallint,
  notes             text,                -- e.g. "Voted with party whip"

  source_url        text,                -- Hansard division record URL
  source_verified   boolean DEFAULT false, -- manually verified vs scraped
  created_at        timestamptz DEFAULT now(),

  UNIQUE(mp_id, bill_id, reading_stage)
);

CREATE INDEX IF NOT EXISTS idx_votes_mp
  ON mp_votes(mp_id, vote_date DESC);
CREATE INDEX IF NOT EXISTS idx_votes_bill
  ON mp_votes(bill_id, vote);
CREATE INDEX IF NOT EXISTS idx_votes_bill_number
  ON mp_votes(bill_number);
CREATE INDEX IF NOT EXISTS idx_votes_date
  ON mp_votes(vote_date DESC);

-- ── 5. MP parliamentary statements (Hansard excerpts) ─────────────────────
-- Each row is one statement/speech by an MP in a sitting
CREATE TABLE IF NOT EXISTS mp_statements (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  mp_id             uuid NOT NULL REFERENCES mp_profiles(id) ON DELETE CASCADE,
  sitting_id        text,                -- Hansard sitting reference
  sitting_date      date NOT NULL,
  parliament_no     smallint,
  session_no        smallint,

  -- Content
  statement_type    varchar(32),
  -- question | oral_question | written_question | debate | motion | point_of_order | ministerial_statement
  topic_category    varchar(32),         -- domain tag: tax | epf | healthcare | etc.
  statement_bm      text,               -- original BM text
  statement_en      text,               -- English translation if available
  word_count        int,

  -- References
  bill_number       text,               -- if statement was about a specific bill
  source_url        text,               -- Hansard page URL
  hansard_page      text,               -- physical page reference in PDF
  created_at        timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_statements_mp
  ON mp_statements(mp_id, sitting_date DESC);
CREATE INDEX IF NOT EXISTS idx_statements_type
  ON mp_statements(statement_type);
CREATE INDEX IF NOT EXISTS idx_statements_topic
  ON mp_statements(topic_category);
CREATE INDEX IF NOT EXISTS idx_statements_date
  ON mp_statements(sitting_date DESC);
CREATE INDEX IF NOT EXISTS idx_statements_fts
  ON mp_statements USING gin(
    to_tsvector('english',
      coalesce(statement_en,'') || ' ' ||
      coalesce(statement_bm,'')
    )
  );

-- ── 6. Committee memberships ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS mp_committee_memberships (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  mp_id           uuid NOT NULL REFERENCES mp_profiles(id) ON DELETE CASCADE,
  committee_name  text NOT NULL,
  role            varchar(32),       -- chairman | deputy_chairman | member
  parliament_no   smallint,
  start_date      date,
  end_date        date,
  is_current      boolean DEFAULT true,
  created_at      timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_committee_mp ON mp_committee_memberships(mp_id);

-- ── 7. Hansard sittings registry ───────────────────────────────────────────
-- One row per parliament sitting day
CREATE TABLE IF NOT EXISTS hansard_sittings (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  sitting_id        text UNIQUE NOT NULL, -- e.g. "DR.24.07.2025"
  sitting_date      date NOT NULL,
  parliament_no     smallint,
  session_no        smallint,
  chamber           varchar(16) DEFAULT 'dewan_rakyat', -- dewan_rakyat | dewan_negara
  pdf_url           text,
  page_count        int,
  ingested          boolean DEFAULT false,
  ingested_at       timestamptz,
  total_statements  int DEFAULT 0,
  created_at        timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_sittings_date
  ON hansard_sittings(sitting_date DESC);
CREATE INDEX IF NOT EXISTS idx_sittings_ingested
  ON hansard_sittings(ingested, sitting_date DESC);

-- ── 8. document_chunks.clause_reference + hansard_segments view ───────────
-- clause_reference generalises beyond Hansard (any ingested source that has
-- an internal pinpoint reference — a Hansard page, a gazette clause, a bill
-- section) so it is added to document_chunks itself, not a Hansard-only
-- side table.
ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS clause_reference text;

-- These WOULD BE document_chunks with domain='hansard' once a follow-up PR
-- widens the valid_domain CHECK constraint and builds the ingestion
-- pipeline (see domain-list decision above). Until then this view is
-- honestly empty: 'hansard' is rejected at insert time by the existing
-- 016 constraint, so no rows can exist with that domain yet.
CREATE VIEW hansard_segments AS
  SELECT
    dc.id,
    dc.content,
    dc.source_title,
    dc.source_url,
    dc.clause_reference AS sitting_reference,
    dc.created_at,
    mp.id              AS mp_id,
    mp.full_name       AS mp_name,
    mp.party           AS mp_party,
    mp.constituency_code,
    mp.constituency_name
  FROM document_chunks dc
  LEFT JOIN mp_profiles mp
    ON dc.source_title ILIKE '%' || mp.full_name || '%'
  WHERE dc.domain = 'hansard';

-- ── 9. Constituency lookup table ───────────────────────────────────────────
-- All 222 parliamentary constituencies + 587 state constituencies
CREATE TABLE IF NOT EXISTS constituencies (
  code          text PRIMARY KEY,    -- "P001", "N.28"
  name          text NOT NULL,
  name_bm       text,
  type          varchar(16),         -- parliament | adun
  state         text,
  region        text,                -- e.g. "Sabah", "Klang Valley"
  registered_voters int,
  last_election text                 -- e.g. "GE15"
);

CREATE INDEX IF NOT EXISTS idx_const_state  ON constituencies(state);
CREATE INDEX IF NOT EXISTS idx_const_type   ON constituencies(type);
CREATE INDEX IF NOT EXISTS idx_const_fts
  ON constituencies USING gin(to_tsvector('english', coalesce(name,'') || ' ' || coalesce(name_bm,'')));

-- ── 10. Useful aggregate functions ─────────────────────────────────────────

-- Get MP voting summary for a bill
CREATE OR REPLACE FUNCTION get_bill_vote_summary(p_bill_number text)
RETURNS TABLE (
  vote          text,
  vote_count    bigint,
  party_breakdown jsonb
) LANGUAGE sql STABLE AS $$
  SELECT
    vote,
    COUNT(*)                                                         AS vote_count,
    jsonb_object_agg(party, party_count) FILTER (WHERE party IS NOT NULL) AS party_breakdown
  FROM (
    SELECT
      v.vote,
      p.party,
      COUNT(*) AS party_count
    FROM mp_votes v
    JOIN mp_profiles p ON p.id = v.mp_id
    WHERE v.bill_number = p_bill_number
    GROUP BY v.vote, p.party
  ) sub
  GROUP BY vote
  ORDER BY vote_count DESC;
$$;

-- Get constituency MP with latest vote summary
CREATE OR REPLACE FUNCTION get_mp_by_constituency(p_code text)
RETURNS TABLE (
  mp_id              uuid,
  full_name          text,
  party              text,
  constituency_name  text,
  attendance_rate    float,
  questions_count    int,
  bills_sponsored    int,
  recent_votes       jsonb
) LANGUAGE sql STABLE AS $$
  SELECT
    p.id,
    p.full_name,
    p.party,
    p.constituency_name,
    p.attendance_rate,
    p.questions_count,
    p.bills_sponsored,
    (
      SELECT jsonb_agg(
        jsonb_build_object(
          'bill', v.bill_title_en,
          'vote', v.vote,
          'date', v.vote_date
        ) ORDER BY v.vote_date DESC
      )
      FROM (
        SELECT * FROM mp_votes
        WHERE mp_id = p.id
        ORDER BY vote_date DESC
        LIMIT 5
      ) v
    ) AS recent_votes
  FROM mp_profiles p
  WHERE p.constituency_code = p_code
    AND p.is_active = true
  LIMIT 1;
$$;

-- ── 11. RLS policies ───────────────────────────────────────────────────────
ALTER TABLE parliament_sessions  ENABLE ROW LEVEL SECURITY;
ALTER TABLE mp_profiles          ENABLE ROW LEVEL SECURITY;
ALTER TABLE parliament_bills     ENABLE ROW LEVEL SECURITY;
ALTER TABLE mp_votes             ENABLE ROW LEVEL SECURITY;
ALTER TABLE mp_statements        ENABLE ROW LEVEL SECURITY;
ALTER TABLE mp_committee_memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE hansard_sittings     ENABLE ROW LEVEL SECURITY;
ALTER TABLE constituencies       ENABLE ROW LEVEL SECURITY;

-- All MP data is public read
CREATE POLICY "parliament_sessions_public_read"
  ON parliament_sessions FOR SELECT TO anon, authenticated USING (true);
CREATE POLICY "mp_profiles_public_read"
  ON mp_profiles FOR SELECT TO anon, authenticated USING (true);
CREATE POLICY "parliament_bills_public_read"
  ON parliament_bills FOR SELECT TO anon, authenticated USING (true);
CREATE POLICY "mp_votes_public_read"
  ON mp_votes FOR SELECT TO anon, authenticated USING (true);
CREATE POLICY "mp_statements_public_read"
  ON mp_statements FOR SELECT TO anon, authenticated USING (true);
CREATE POLICY "mp_committee_public_read"
  ON mp_committee_memberships FOR SELECT TO anon, authenticated USING (true);
CREATE POLICY "hansard_sittings_public_read"
  ON hansard_sittings FOR SELECT TO anon, authenticated USING (true);
CREATE POLICY "constituencies_public_read"
  ON constituencies FOR SELECT TO anon, authenticated USING (true);

-- Only service role can write (ingestion pipeline)
-- No additional INSERT/UPDATE policies needed — service role bypasses RLS
