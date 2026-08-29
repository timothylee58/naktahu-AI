-- ScamShield: adds the 'scam_check' domain (Trap #6 — this migration plus
-- the two Python _VALID_DOMAINS copies, router_node.py and ingest_feed.py,
-- move together) and official_gov_domains, the reference table the new
-- scam_check_agent (app/agents/scam_check_agent/) looks up against.
--
-- Scope decision (see the PR this ships in): scam_check is added as a
-- canonical domain for consistency with every other vertical agent having
-- one (parliament/welfare/property all do), and to leave room for future
-- general scam-awareness content ingested via ingest_feed.py. No content is
-- ingested by this migration — document_chunks gets zero new rows, same
-- "schema first, content later" deferral migration 025 used for parliament.
-- scam_check_agent itself never queries document_chunks or routes through
-- rag_node: it's a standalone single-shot agent (same shape as
-- welfare-eligibility-agent), not a chat-routed RAG domain.
--
-- official_gov_domains is the safety-critical artifact here: an "official"
-- verdict must come from this curated, human-maintained list, never from an
-- LLM guess (see check_node.py's docstring). Seeded with Malaysia's most
-- commonly impersonated government agencies, statutory bodies, and banks —
-- NOT exhaustive, and deliberately excludes any domain the author has not
-- personally verified resolves to that institution's real site. A domain
-- NOT in this table is reported as "unverified", never as "unofficial" or
-- "safe" — absence of a match is not evidence of fraud, only of an
-- unmaintained list (see check_node.py's verdict logic).

ALTER TABLE document_chunks DROP CONSTRAINT IF EXISTS valid_domain;
ALTER TABLE document_chunks ADD CONSTRAINT valid_domain CHECK (
  domain IN (
    'government', 'education', 'legal', 'finance', 'healthcare',
    'epf', 'tax', 'business', 'immigration', 'culture', 'parliament',
    'property', 'welfare', 'scam_check'
  )
);

CREATE TABLE IF NOT EXISTS official_gov_domains (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  institution_name      text NOT NULL,
  institution_name_bm   text,
  domain                text NOT NULL UNIQUE,   -- e.g. 'hasil.gov.my' — normalised lowercase, no scheme/path/www
  agency_type           varchar(24) NOT NULL CHECK (agency_type IN ('government', 'statutory_body', 'bank', 'postal')),
  category              text,                   -- loose label (tax, epf, immigration, ...) — not FK'd to valid_domain
  common_scam_patterns  text[],                 -- e.g. '{fake refund SMS, fake summons link}'
  official_contact      text,
  created_at            timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_official_gov_domains_domain ON official_gov_domains(domain);

ALTER TABLE official_gov_domains ENABLE ROW LEVEL SECURITY;
-- Public reference data — same reasoning as constituencies (025): a citizen
-- checking "is this the real LHDN site" needs to be able to read this list
-- directly, not just through the agent.
CREATE POLICY "official_gov_domains_public_read"
  ON official_gov_domains FOR SELECT TO anon, authenticated USING (true);

-- Confirmed bug (automated review): load_agent_registry reads the live
-- `agents` table in production (services/agent_registry.py) — the flat
-- fallback dict in that same file only covers dev/tests when Supabase is
-- unreachable. Without this row, POST /api/v1/agents/scam-check-agent/start
-- 404s in production even though the handler and fallback registry exist.
-- Same pattern as migration 041's property-concierge insert.
INSERT INTO agents (name, description, input_schema, plan_required, credit_cost)
VALUES (
    'scam-check-agent',
    'Checks a pasted SMS/link/phone number claiming to be from a government agency or bank against a curated list of verified official domains.',
    '{}',
    'free',
    0
)
ON CONFLICT (name) DO NOTHING;

INSERT INTO official_gov_domains (institution_name, institution_name_bm, domain, agency_type, category, common_scam_patterns, official_contact) VALUES
  ('Inland Revenue Board (LHDN)', 'Lembaga Hasil Dalam Negeri', 'hasil.gov.my', 'government', 'tax',
    '{fake tax refund SMS, fake e-Filing login link, fake "outstanding tax" WhatsApp message}', 'https://www.hasil.gov.my'),
  ('LHDN e-Filing', 'e-Filing LHDN', 'ezhasil.gov.my', 'government', 'tax',
    '{fake e-Filing login page, phishing link mimicking ezhasil}', 'https://ezhasil.gov.my'),
  ('Road Transport Department (JPJ)', 'Jabatan Pengangkutan Jalan', 'jpj.gov.my', 'government', 'government',
    '{fake summons/saman payment link, fake licence renewal SMS}', 'https://www.jpj.gov.my'),
  ('Employees Provident Fund (EPF/KWSP)', 'Kumpulan Wang Simpanan Pekerja', 'kwsp.gov.my', 'statutory_body', 'epf',
    '{fake EPF withdrawal approval link, fake i-Akaun login page, fake "your KWSP account is locked" call}', 'https://www.kwsp.gov.my'),
  ('Social Security Organisation (SOCSO/PERKESO)', 'Pertubuhan Keselamatan Sosial', 'perkeso.gov.my', 'statutory_body', 'epf',
    '{fake SOCSO claim approval SMS, fake compensation payout link}', 'https://www.perkeso.gov.my'),
  ('Royal Malaysia Police (PDRM)', 'Polis DiRaja Malaysia', 'rmp.gov.my', 'government', 'government',
    '{fake police report/summons call, "your IC was used in a crime" scam call}', 'https://www.rmp.gov.my'),
  ('Bank Negara Malaysia', 'Bank Negara Malaysia', 'bnm.gov.my', 'government', 'finance',
    '{fake BNM "your bank account is under investigation" call, fake BNM licensing verification link}', 'https://www.bnm.gov.my'),
  ('National Registration Department (JPN)', 'Jabatan Pendaftaran Negara', 'jpn.gov.my', 'government', 'government',
    '{fake MyKad renewal link, fake "IC suspended" SMS}', 'https://www.jpn.gov.my'),
  ('Immigration Department of Malaysia', 'Jabatan Imigresen Malaysia', 'imi.gov.my', 'government', 'immigration',
    '{fake passport renewal link, fake visa/permit fine payment SMS}', 'https://www.imi.gov.my'),
  ('Companies Commission of Malaysia (SSM)', 'Suruhanjaya Syarikat Malaysia', 'ssm.com.my', 'statutory_body', 'business',
    '{fake company registration renewal invoice, fake "your SSM registration will be suspended" email}', 'https://www.ssm.com.my'),
  ('Pos Malaysia', 'Pos Malaysia', 'pos.com.my', 'postal', 'government',
    '{fake parcel customs-fee payment link, fake "parcel held" SMS}', 'https://www.pos.com.my'),
  ('Ministry of Health (MOH) / MySejahtera', 'Kementerian Kesihatan Malaysia', 'moh.gov.my', 'government', 'healthcare',
    '{fake MySejahtera update link, fake vaccination certificate scam}', 'https://www.moh.gov.my'),
  ('Maybank', 'Maybank', 'maybank2u.com.my', 'bank', 'finance',
    '{fake Maybank2u login page, fake "your account is frozen" SMS}', 'https://www.maybank2u.com.my'),
  ('CIMB Bank', 'CIMB Bank', 'cimbclicks.com.my', 'bank', 'finance',
    '{fake CIMB Clicks login page, fake OTP request call}', 'https://www.cimbclicks.com.my'),
  ('Public Bank', 'Public Bank', 'pbebank.com', 'bank', 'finance',
    '{fake PBe login page, fake "suspicious transaction" SMS}', 'https://www.pbebank.com');
