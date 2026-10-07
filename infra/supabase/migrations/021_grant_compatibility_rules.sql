-- =============================================================================
-- Migration 021: Grant compatibility rules (three-state stacking intelligence)
--
-- WHY: grant_database.stackable_with / conflicts_with are text[] columns that
-- can only express a BINARY verdict (compatible / incompatible). The real
-- Malaysian grant landscape has a third, more common state: two programmes a
-- founder may legitimately hold at the same time but may NOT claim against the
-- same project cost or expense line (the matching-grant family — MDAG, SDMG,
-- MSME Digital Grant MADANI — is the canonical example). The arrays also carry
-- no explanation, no scope, no source, and no verification date, so nothing in
-- the product can tell a founder *why* a pair is restricted.
--
-- This table models a pair rule as a first-class row: undirected, three-state,
-- scoped, explained bilingually, and sourced. It COMPLEMENTS the arrays rather
-- than replacing them — app/agents/eligibility_agent/compatibility.py falls
-- back to the arrays when this table is absent (Trap #5: migrations are files,
-- not reality, so the backend must degrade rather than crash).
--
-- Seed policy: every 'stackable' and 'conflict' row below is derived from the
-- stackable_with / conflicts_with arrays already seeded in migration 020, so
-- the two sources agree by construction. Array entries in 020 use informal
-- aliases ('MDEC MDAG', 'Cradle CIP Sprint', 'MATRADE MDG', ...) that do not
-- match the canonical programme_name values; they are canonicalised here (and
-- in compatibility.py's alias map). 'partial_overlap' rows are NOT in 020 —
-- each one's explanation states plainly that it is a conservative policy
-- default, not a citation, and source_url points at the programme's own page.
-- No citation URL is fabricated (CLAUDE.md hard rule).
-- =============================================================================

CREATE TABLE IF NOT EXISTS grant_compatibility_rules (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  programme_a     text NOT NULL,
  programme_b     text NOT NULL,
  rule_type       varchar(16) NOT NULL,
  overlap_scope   text,          -- e.g. 'same_project_cost'; NULL for stackable/conflict
  explanation_en  text,
  explanation_bm  text,
  source_url      text,
  last_verified   date,
  created_at      timestamptz DEFAULT now(),
  updated_at      timestamptz DEFAULT now(),
  CONSTRAINT grant_compat_rule_type_valid
    CHECK (rule_type IN ('stackable', 'partial_overlap', 'conflict')),
  CONSTRAINT grant_compat_not_self CHECK (programme_a <> programme_b)
);

-- Rules are UNDIRECTED: (A,B) and (B,A) are the same rule. A normalised unique
-- index on the sorted pair makes the duplicate physically impossible.
CREATE UNIQUE INDEX IF NOT EXISTS idx_grant_compat_pair_unique
  ON grant_compatibility_rules (
    LEAST(programme_a, programme_b),
    GREATEST(programme_a, programme_b)
  );

-- Lookup by either endpoint (the checker queries with an IN () on both columns).
CREATE INDEX IF NOT EXISTS idx_grant_compat_programme_a
  ON grant_compatibility_rules (programme_a);
CREATE INDEX IF NOT EXISTS idx_grant_compat_programme_b
  ON grant_compatibility_rules (programme_b);

-- ── Seed ───────────────────────────────────────────────────────────────────
INSERT INTO grant_compatibility_rules (
  programme_a, programme_b, rule_type, overlap_scope,
  explanation_en, explanation_bm, source_url, last_verified
) VALUES

-- ── CONFLICTS (both derived from migration 020 conflicts_with arrays) ──────
(
  'CIP Spark', 'CIP Sprint', 'conflict', NULL,
  'Cradle''s CIP programmes are stage-gated: Spark funds idea-to-prototype and Sprint funds commercialisation of an existing MVP. A company is in one stage at a time, so the two cannot be held concurrently. Graduating from Spark to Sprint is the intended path — apply sequentially, not simultaneously.',
  'Program CIP Cradle adalah berperingkat: Spark membiayai peringkat idea-ke-prototaip manakala Sprint membiayai pengkomersilan MVP sedia ada. Syarikat berada pada satu peringkat sahaja pada satu-satu masa, jadi kedua-duanya tidak boleh dipegang serentak. Naik taraf dari Spark ke Sprint adalah laluan yang dimaksudkan — mohon secara berturutan, bukan serentak.',
  'https://cradle.com.my/programmes', '2026-07-01'
),
(
  'SME Digitalization Grant (SDMG)', 'MSME Digital Grant MADANI', 'conflict', NULL,
  'Both are 50% matching grants of up to RM5,000 for the same category of SME digitalisation spend, administered under separate initiatives. An SME is entitled to the digitalisation matching grant once — holding both is treated as duplicate funding of the same entitlement.',
  'Kedua-duanya adalah geran padanan 50% sehingga RM5,000 untuk kategori perbelanjaan pendigitalan PKS yang sama, di bawah inisiatif berasingan. PKS layak menerima geran padanan pendigitalan sekali sahaja — memegang kedua-duanya dikira sebagai pembiayaan berganda bagi kelayakan yang sama.',
  'https://www.mdec.my/godigital', '2026-07-01'
),

-- ── PARTIAL OVERLAPS (conservative policy defaults, not published rules) ───
(
  'Malaysia Digital Acceleration Grant (MDAG)', 'SME Digitalization Grant (SDMG)', 'partial_overlap', 'same_project_cost',
  'Both are matching grants that reimburse a share of digitalisation spend, so the same invoice or project cost cannot be claimed under both. You may hold both, but each expense line must be allocated to exactly one grant. NOTE: this is a conservative policy default applied because both are matching grants for overlapping cost categories — it is not a published joint rule. Confirm the cost split with both agencies before submitting.',
  'Kedua-duanya adalah geran padanan yang membayar balik sebahagian perbelanjaan pendigitalan, jadi invois atau kos projek yang sama tidak boleh dituntut di bawah kedua-duanya. Anda boleh memegang kedua-duanya, tetapi setiap butiran perbelanjaan mesti diperuntukkan kepada satu geran sahaja. NOTA: ini adalah anggapan dasar berhemat kerana kedua-duanya geran padanan bagi kategori kos bertindih — bukan peraturan bersama yang diterbitkan. Sahkan pembahagian kos dengan kedua-dua agensi sebelum menghantar permohonan.',
  'https://www.mdec.my/malaysia-digital/mdag', '2026-07-01'
),
(
  'Malaysia Digital Acceleration Grant (MDAG)', 'MSME Digital Grant MADANI', 'partial_overlap', 'same_project_cost',
  'Both are MDEC-administered digitalisation funding. They target different company sizes and ticket sizes, but where the scopes touch (cloud, digital tooling) the same project cost cannot be claimed twice. Hold both if eligible, but keep the expense lines separate. NOTE: conservative policy default for two matching grants from the same agency — not a published joint rule.',
  'Kedua-duanya adalah pembiayaan pendigitalan di bawah MDEC. Sasaran saiz syarikat dan jumlah pembiayaan berbeza, tetapi di mana skop bertindih (awan, alat digital) kos projek yang sama tidak boleh dituntut dua kali. Pegang kedua-duanya jika layak, tetapi asingkan butiran perbelanjaan. NOTA: anggapan dasar berhemat bagi dua geran padanan dari agensi yang sama — bukan peraturan bersama yang diterbitkan.',
  'https://www.mdec.my/godigital', '2026-07-01'
),
(
  'CIP Spark', 'MTDC Sandbox Fund 4', 'partial_overlap', 'same_project_cost',
  'Both fund early-stage R&D and prototype development. They can be held together where they fund distinct work packages, but the same R&D cost cannot be claimed under both, and MTDC''s corporate co-investment requirement means the co-funded portion cannot also be counted as Spark match. NOTE: conservative policy default for two R&D funds with overlapping cost categories — not a published joint rule.',
  'Kedua-duanya membiayai R&D peringkat awal dan pembangunan prototaip. Kedua-duanya boleh dipegang bersama jika membiayai pakej kerja yang berasingan, tetapi kos R&D yang sama tidak boleh dituntut di bawah kedua-duanya, dan syarat pelaburan bersama korporat MTDC bermakna bahagian yang dibiayai bersama tidak boleh dikira sebagai padanan Spark. NOTA: anggapan dasar berhemat bagi dua dana R&D dengan kategori kos bertindih — bukan peraturan bersama yang diterbitkan.',
  'https://www.mtdc.com.my/products-services-listing/sandbox-fund/', '2026-07-01'
),

-- ── STACKABLE (all derived from migration 020 stackable_with arrays) ───────
(
  'CIP Spark', 'SME Digitalization Grant (SDMG)', 'stackable', NULL,
  'Different purposes and different cost bases: Spark funds product development and commercialisation, SDMG reimburses off-the-shelf digitalisation tooling from an approved vendor list. No shared expense line.',
  'Tujuan dan asas kos berbeza: Spark membiayai pembangunan produk dan pengkomersilan, SDMG membayar balik alat pendigitalan siap sedia daripada senarai vendor yang diluluskan. Tiada butiran perbelanjaan yang dikongsi.',
  'https://cradle.com.my/programmes', '2026-07-01'
),
(
  'CIP Spark', 'Market Development Grant (MDG)', 'stackable', NULL,
  'MDG reimburses export-market promotion costs (trade fairs, overseas marketing); Spark funds product development. Distinct cost categories, no double-claim risk.',
  'MDG membayar balik kos promosi pasaran eksport (pameran perdagangan, pemasaran luar negara); Spark membiayai pembangunan produk. Kategori kos berbeza, tiada risiko tuntutan berganda.',
  'https://www.matrade.gov.my/en/malaysian-exporters/going-global/market-development-grant', '2026-07-01'
),
(
  'CIP Spark', 'Malaysia Digital Acceleration Grant (MDAG)', 'stackable', NULL,
  'MDAG requires Malaysia Digital registration and funds adoption of AI/blockchain/IoT/quantum capability; Spark funds early product development. Commonly combined by MD-status startups.',
  'MDAG memerlukan pendaftaran Malaysia Digital dan membiayai penggunaan keupayaan AI/blockchain/IoT/kuantum; Spark membiayai pembangunan produk awal. Lazim digabungkan oleh syarikat pemula berstatus MD.',
  'https://www.mdec.my/malaysia-digital/mdag', '2026-07-01'
),
(
  'CIP Sprint', 'Market Development Grant (MDG)', 'stackable', NULL,
  'Sprint funds commercialisation of an existing MVP; MDG reimburses export-market development for a product already going to market. Complementary, distinct cost bases.',
  'Sprint membiayai pengkomersilan MVP sedia ada; MDG membayar balik pembangunan pasaran eksport bagi produk yang sudah dipasarkan. Saling melengkapi, asas kos berbeza.',
  'https://www.matrade.gov.my/en/malaysian-exporters/going-global/market-development-grant', '2026-07-01'
),
(
  'CIP Sprint', 'Malaysia Digital Acceleration Grant (MDAG)', 'stackable', NULL,
  'Sprint funds commercialisation milestones; MDAG funds digital-capability adoption under Malaysia Digital. Different agencies, different deliverables, different cost lines.',
  'Sprint membiayai pencapaian pengkomersilan; MDAG membiayai penggunaan keupayaan digital di bawah Malaysia Digital. Agensi, penyampaian dan butiran kos yang berbeza.',
  'https://www.mdec.my/malaysia-digital/mdag', '2026-07-01'
),
(
  'CIP Sprint', 'MTDC Sandbox Fund 4', 'stackable', NULL,
  'MTDC Sandbox Fund is explicitly designed to sit alongside Cradle commercialisation funding, with the corporate co-investor covering the matching portion. Structured as complementary rather than competing capital.',
  'MTDC Sandbox Fund direka khusus untuk berjalan seiring dengan pembiayaan pengkomersilan Cradle, dengan pelabur korporat menampung bahagian padanan. Distrukturkan sebagai modal saling melengkapi, bukan bersaing.',
  'https://www.mtdc.com.my/products-services-listing/sandbox-fund/', '2026-07-01'
),
(
  'SME Digitalization Grant (SDMG)', 'HRD Corp Training Fund', 'stackable', NULL,
  'SDMG funds the digital tool or system; HRD Corp funds the levy-registered training to use it. Separate claim streams, and HRD Corp draws on the employer''s own levy account rather than the grant budget.',
  'SDMG membiayai alat atau sistem digital; HRD Corp membiayai latihan berdaftar levi untuk menggunakannya. Aliran tuntutan berasingan, dan HRD Corp menggunakan akaun levi majikan sendiri, bukan bajet geran.',
  'https://www.hrdcorp.gov.my', '2026-07-01'
),
(
  'SME Digitalization Grant (SDMG)', 'Market Development Grant (MDG)', 'stackable', NULL,
  'SDMG covers domestic digitalisation tooling; MDG reimburses export-market promotion. No overlap in eligible cost categories.',
  'SDMG merangkumi alat pendigitalan domestik; MDG membayar balik promosi pasaran eksport. Tiada pertindihan dalam kategori kos yang layak.',
  'https://www.smecorp.gov.my', '2026-07-01'
),
(
  'MSME Digital Grant MADANI', 'HRD Corp Training Fund', 'stackable', NULL,
  'The MADANI digital grant funds the tool; HRD Corp funds training delivered against the employer''s levy account. Different funding sources and claim processes.',
  'Geran digital MADANI membiayai alat tersebut; HRD Corp membiayai latihan yang disampaikan melalui akaun levi majikan. Sumber pembiayaan dan proses tuntutan yang berbeza.',
  'https://www.hrdcorp.gov.my', '2026-07-01'
),
(
  'SME Automation & Digitalization Facility (ADF)', 'Malaysia Digital Acceleration Grant (MDAG)', 'stackable', NULL,
  'ADF is a BNM financing facility (repayable soft loan), not a grant, so it does not consume grant entitlement. It is routinely used to fund the company''s own share of a matching-grant project such as MDAG.',
  'ADF ialah kemudahan pembiayaan BNM (pinjaman mudah yang perlu dibayar balik), bukan geran, jadi ia tidak menggunakan kelayakan geran. Ia lazim digunakan untuk membiayai bahagian syarikat sendiri dalam projek geran padanan seperti MDAG.',
  'https://www.bnm.gov.my/funds-for-smes', '2026-07-01'
),
(
  'HRD Corp Training Fund', 'Malaysia Digital Acceleration Grant (MDAG)', 'stackable', NULL,
  'MDAG funds the technology adoption project; HRD Corp funds the workforce training that accompanies it, drawn from the employer''s levy. Separate budgets and claim channels.',
  'MDAG membiayai projek penggunaan teknologi; HRD Corp membiayai latihan tenaga kerja yang mengiringinya, diambil daripada levi majikan. Bajet dan saluran tuntutan berasingan.',
  'https://www.hrdcorp.gov.my', '2026-07-01'
)
ON CONFLICT DO NOTHING;

-- ── RLS — public reference data, read-only to everyone ─────────────────────
ALTER TABLE grant_compatibility_rules ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "grant_compatibility_rules_public_read" ON grant_compatibility_rules;
CREATE POLICY "grant_compatibility_rules_public_read"
  ON grant_compatibility_rules FOR SELECT
  TO anon, authenticated
  USING (true);
