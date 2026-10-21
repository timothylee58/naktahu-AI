-- =============================================================================
-- Migration 060: Mandarin (Simplified) explanations for grant compatibility rules
--
-- WHY: migration 021 stores each stacking rule's explanation in English and Bahasa
-- Malaysia only. The Grant Finder UI and the Eligibility Agent now answer in
-- Mandarin (zh), but a zh user was shown the English explanation for every pair
-- because the table had no zh column. This adds explanation_zh and fills it for
-- all 16 rules seeded in 021.
--
-- Safe to apply in any order relative to the app deploy:
--   * the backend reads rules with select("*") and falls back to the English text
--     when explanation_zh is absent or NULL (compatibility.py::_explanation), so
--     nothing breaks before this is applied;
--   * the UPDATE only fills rows where explanation_zh IS NULL, so re-running it
--     never overwrites a later hand edit.
--
-- The three 'partial_overlap' texts keep the English/BM caveat that they are a
-- conservative policy default, NOT a published joint rule (CLAUDE.md: no fabricated
-- citation). source_url / last_verified are unchanged. Wording follows the
-- existing zh UI terms (补助金, 可叠加). Native-speaker review is still advisable.
-- =============================================================================

ALTER TABLE grant_compatibility_rules
  ADD COLUMN IF NOT EXISTS explanation_zh text;

UPDATE grant_compatibility_rules AS r
SET explanation_zh = v.zh,
    updated_at = now()
FROM (VALUES

-- ── CONFLICTS ──────────────────────────────────────────────────────────────
(
  'CIP Spark', 'CIP Sprint',
  'Cradle 的 CIP 计划按阶段推进：Spark 资助从创意到原型阶段，Sprint 资助现有 MVP 的商业化。公司同一时间只处于一个阶段，因此两者不能同时持有。从 Spark 晋级到 Sprint 是预期路径——请依次申请，而不是同时申请。'
),
(
  'SME Digitalization Grant (SDMG)', 'MSME Digital Grant MADANI',
  '两者都是针对同一类中小企业数码化支出、最高 RM5,000 的 50% 配对补助金，分属不同的倡议。中小企业只能享有一次数码化配对补助金的资格——同时持有两者会被视为对同一资格的重复资助。'
),

-- ── PARTIAL OVERLAPS (conservative policy defaults, not published rules) ───
(
  'Malaysia Digital Acceleration Grant (MDAG)', 'SME Digitalization Grant (SDMG)',
  '两者都是报销一部分数码化支出的配对补助金，因此同一张发票或同一项目成本不能在两项补助金下重复申领。您可以同时持有两者，但每一项支出必须只分配给其中一项补助金。注意：这是一项审慎的保守政策默认值，原因是两者都是成本类别重叠的配对补助金——并非已公布的联合规则。提交申请前，请先与两家机构确认成本分摊方式。'
),
(
  'Malaysia Digital Acceleration Grant (MDAG)', 'MSME Digital Grant MADANI',
  '两者都是由 MDEC 管理的数码化资助。它们面向的公司规模和资助额度不同，但在范围重叠之处（云端、数码工具），同一项目成本不能申领两次。符合资格时可同时持有，但请将支出项目分开。注意：这是针对同一机构两项配对补助金的保守政策默认值——并非已公布的联合规则。'
),
(
  'CIP Spark', 'MTDC Sandbox Fund 4',
  '两者都资助早期研发和原型开发。若资助的是不同的工作包，可以同时持有，但同一项研发成本不能在两者下重复申领；而且由于 MTDC 要求企业共同投资，共同出资的部分也不能再算作 Spark 的配对出资。注意：这是针对两项成本类别重叠的研发基金的保守政策默认值——并非已公布的联合规则。'
),

-- ── STACKABLE ──────────────────────────────────────────────────────────────
(
  'CIP Spark', 'SME Digitalization Grant (SDMG)',
  '用途和成本基础不同：Spark 资助产品开发和商业化，SDMG 则报销来自核准供应商名单的现成数码化工具。没有共同的支出项目。'
),
(
  'CIP Spark', 'Market Development Grant (MDG)',
  'MDG 报销出口市场推广成本（贸易展览会、海外营销）；Spark 资助产品开发。成本类别不同，没有重复申领的风险。'
),
(
  'CIP Spark', 'Malaysia Digital Acceleration Grant (MDAG)',
  'MDAG 要求具备 Malaysia Digital 注册，并资助企业采用 AI/区块链/物联网/量子能力；Spark 资助早期产品开发。具备 MD 身份的初创公司经常将两者结合使用。'
),
(
  'CIP Sprint', 'Market Development Grant (MDG)',
  'Sprint 资助现有 MVP 的商业化；MDG 报销已进入市场的产品所需的出口市场开发费用。两者互补，成本基础不同。'
),
(
  'CIP Sprint', 'Malaysia Digital Acceleration Grant (MDAG)',
  'Sprint 资助商业化里程碑；MDAG 资助在 Malaysia Digital 框架下采用数码能力。机构、交付成果和成本项目均不相同。'
),
(
  'CIP Sprint', 'MTDC Sandbox Fund 4',
  'MTDC Sandbox Fund 的设计本就是与 Cradle 商业化资助并行，由企业共同投资者承担配对部分。其结构是互补资本，而非相互竞争。'
),
(
  'SME Digitalization Grant (SDMG)', 'HRD Corp Training Fund',
  'SDMG 资助数码工具或系统；HRD Corp 资助使用该工具所需的、已登记征费的培训。两者是各自独立的申领渠道，而且 HRD Corp 动用的是雇主自己的征费账户，而非补助金预算。'
),
(
  'SME Digitalization Grant (SDMG)', 'Market Development Grant (MDG)',
  'SDMG 涵盖国内的数码化工具；MDG 报销出口市场推广费用。符合资格的成本类别没有重叠。'
),
(
  'MSME Digital Grant MADANI', 'HRD Corp Training Fund',
  'MADANI 数码补助金资助工具本身；HRD Corp 资助从雇主征费账户中支付的培训。资金来源和申领流程不同。'
),
(
  'SME Automation & Digitalization Facility (ADF)', 'Malaysia Digital Acceleration Grant (MDAG)',
  'ADF 是 BNM 的融资便利（须偿还的优惠贷款），不是补助金，因此不会占用补助金资格。它常被用来支付公司在 MDAG 这类配对补助金项目中自行承担的部分。'
),
(
  'HRD Corp Training Fund', 'Malaysia Digital Acceleration Grant (MDAG)',
  'MDAG 资助技术采用项目；HRD Corp 资助与之配套的员工培训，款项取自雇主的征费。预算和申领渠道各自独立。'
)

) AS v(a, b, zh)
WHERE LEAST(r.programme_a, r.programme_b) = LEAST(v.a, v.b)
  AND GREATEST(r.programme_a, r.programme_b) = GREATEST(v.a, v.b)
  AND r.explanation_zh IS NULL;
