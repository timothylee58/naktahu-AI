# Product roadmap notes

**Status:** exploratory product-direction notes, not a committed roadmap. Nothing here is scheduled or promised; it's a working set of ideas plus enough of a technical sketch that a future session (human or AI agent) can pick one up and scope it properly before building.

---

## The USP this points to

NakTahu is the trilingual AI query layer sitting across Malaysia's 7+ siloed government apps and portals (MyEG, e-Filing, EPF i-Akaun, KWSP, SSM, JPJ, MyDigital ID, and more) — not a replacement for any single one, but the thing that tells a citizen which one they need, in their language, with a citation.

SITI@1MOCC already tried to be a "directory" of government services, but it's static and BM/EN only, with no reasoning over the user's actual situation. That's the wedge:

> "Don't memorize which of 8 government apps has your answer — ask NakTahu once."

Every feature below is evaluated against that wedge: does it make NakTahu a better *query layer across* existing official systems, or does it start turning NakTahu into a replacement for one of them? The former is the strategy; the latter is scope creep this product should avoid (rebuilding e-Filing or i-Akaun is not the plan — deep-linking into them is).

---

## Near-term, high-confidence additions

### 1. Rate & Deadline Tracker

A small persistent widget — think Malaysia4U's KLCI/forex ticker, but civic-relevant: current EPF dividend rate, SST rate, minimum wage, subsidised fuel ceiling price, tax filing deadlines. These are exactly the facts people currently Google and get stale results for.

**Why it fits:** pairs directly with the existing `effective_date`/`superseded_by` temporal-accuracy machinery already built into the RAG pipeline (`document_chunks`, `analyst_node`'s confidence gate) — this is largely a presentation layer over data the ingestion pipeline is already designed to keep current, not a new data problem.

**Existing building block:** `deadline-monitor` agent (`apps/api/services/agent_registry.py`, `apps/web/src/app/agents/deadline-monitor/`) and the `deadline_schedule` table already back a `/api/v1/agents/deadline-monitor/deadlines` list endpoint (`apps/api/app/routers/agents.py`). The gap is *rates* (EPF dividend %, SST %, minimum wage, fuel ceiling) — there's no `rate_schedule`-equivalent table today, only deadlines.

**How an AI agent could explore this:**
1. Read `apps/api/app/routers/agents.py`'s `list_deadlines` endpoint and `infra/supabase/migrations/` for `deadline_schedule`'s schema as the template.
2. Design a new `rate_schedule` table (or widen `deadline_schedule` with a `kind: 'deadline' | 'rate'` discriminator plus a `value`/`unit` column) — the widen approach avoids a second near-identical table and a second ingestion path; evaluate both against Trap #5 (new migration either way) before committing.
3. Register 1-2 real ingestion sources (EPF dividend announcements, LHDN SST rate page) via `scripts/sources.py` + `scripts/ingest_feed.py`, following the same injection-scan and `content_hash` dedup rules as any other source (Trap #14).
4. Frontend: a compact widget component (sidebar or dashboard header), reusing `DeadlineWidget.tsx`'s data-fetching shape rather than inventing a new pattern.
5. Scope check before building: confirm at least 2-3 rates have a genuinely trackable official source with a real "as of" date — a widget with stale or unsourced numbers is worse than no widget, given this product's trust USP.

### 2. Deep-link handoff

When NakTahu resolves an answer that requires an actual transaction — EPF withdrawal, e-Filing, MyDigital ID registration — deep-link straight into the relevant official app/portal instead of just naming it. Mirrors how TNG eWallet hooks into foodpanda/Klook/KLIA Ekspres as partner integrations rather than rebuilding them.

**Why it fits:** this is the clearest expression of the "query layer, not replacement" USP — it makes the boundary between "NakTahu answers" and "government portal executes" explicit and useful, instead of leaving the user to go search for the right portal themselves after getting an answer.

**How an AI agent could explore this:**
1. This is primarily a *data* problem, not a code problem: it needs a maintained mapping of `{transaction intent → official URL}` (e.g. "EPF withdrawal" → `https://www.kwsp.gov.my/...`). Start by auditing which of the existing citation URLs in `document_chunks` already point at actionable pages vs. informational ones — the citation metadata (`{title, ministry, url, confidence}`) may already carry most of what's needed.
2. Add an optional `action_url`/`action_label` field to the citation chip data shape (`CitationChip.tsx`) and to chunk metadata, populated only where a URL genuinely resolves to a transactional entry point — never a guessed URL (this is a direct extension of the existing "never render a fabricated citation URL" hard rule in `CLAUDE.md`).
3. `synthesiser_node` would need to surface this alongside the citation, not replace it — the answer should still explain *what* to do; the deep link is the "now go do it" affordance.
4. Keep this out of `analyst_node`'s confidence-scoring path initially — treat action-URL presence as informational metadata, not something that raises/lowers answer confidence, until there's real usage data to justify otherwise.

### 3. Complaint-drafting agent

CFM's Ez ADU (KPDNKK consumer fraud) and VSP (police reports) show real citizen demand for complaint-filing help. This is a natural sibling to the existing Compliance Drafter — "help me draft a scam/fraud complaint to KPDNKK" is the same shape as "help me draft a compliance report," just citizen-facing instead of business-facing.

**Why it fits:** near-zero new architecture — it's a new vertical agent reusing the Compliance Drafter's graph shape (intake → PDF generation with an HITL confirm step), not a new agent pattern.

**How an AI agent could explore this:**
1. Read `apps/api/app/agents/compliance_drafter/` end-to-end (`nodes.py`, `graph.py`, `state.py`) as the direct template — the `generate_pdf_node`'s `interrupt_before=["generate_pdf"]` HITL pattern is exactly what a complaint draft needs (let the citizen review before a document is generated).
2. New `apps/api/app/agents/complaint_drafter/` module: state fields for complaint type (consumer fraud / police report / other), incident details, involved party, desired outcome; RAG grounding should query `document_chunks` filtered to `domain in ("legal", "government")` for the correct KPDNKK/PDRM procedural facts (what info a valid complaint needs, where to file it) — never let the LLM invent procedural requirements.
3. Register in `agent_registry.py`'s fallback dict + a new migration seeding the `agents` table row (follow migration 031's `retrenchment-navigator` seed as the template) — pick a `plan_required`/`credit_cost` deliberately, this is a judgment call, not a default.
4. Two-mains mount (Trap #1) and full test/i18n checklist per `CLAUDE.md` §6 apply as with any new agent.
5. Sensitive-content note: complaint drafts describe alleged fraud/incidents involving named third parties — worth an explicit read of how `compliance_drafter` currently handles PII in generated documents before extending the pattern to citizen complaints, since the risk profile (naming a private individual as a fraud suspect) is different from a business compliance report.

---

## Medium-term, differentiation-building

### 4. Verified Gov Digest

A narrow, citation-backed weekly digest of only official circulars/policy changes (LHDN, KWSP, MOF), positioned explicitly against Malaysia4U's raw 60-source aggregation as "we only show you what's actually official and current" — reinforcing the trust USP rather than competing on news volume.

**How an AI agent could explore this:**
1. This is closer to a scheduled batch job than a new agent: a weekly query over `document_chunks` filtered to `effective_date` within the last 7 days, across `government`/`tax`/`epf`/`finance` domains, ranked by ministry authority rather than recency alone.
2. No new ingestion pipeline needed — this consumes what `ingest_feed.py` already populates. The work is in selection/ranking logic and a digest-formatting step (email or in-app), not new data sources.
3. Delivery mechanism (email digest vs. an in-app "This Week" panel) is a product decision, not a technical one — flag it back to the user rather than guessing; the two have very different scope (email needs a sending pipeline and unsubscribe/consent handling; an in-app panel doesn't).
4. Explicitly scope this as *read-only synthesis of existing chunks* — no new source registration required to ship a first version, which makes it a good candidate to prototype before committing to #1's new-rate-tracking-source work.

### 5. Guided multi-agency journeys

Chain existing agents into one flow, the way TNG chains ride-hailing → payment → booking: e.g. a single "Starting a Business" journey walking SSM registration → LHDN tax number → EPF/SOCSO employer setup → relevant grants, instead of five separate agent cards a user has to discover on their own.

**Why it fits:** every step in that example journey already has a corresponding agent or RAG-covered domain (`sme-compliance-navigator`, `grant-finder`, `epf`/`tax`/`business` domains) — this is an orchestration/UX layer over existing capability, not new agents.

**How an AI agent could explore this:**
1. This needs a "journey" concept that doesn't exist yet: an ordered sequence of agent invocations (or agent + plain RAG answers) with a shared context object carrying facts forward (e.g. the business type entered in step 1 shouldn't need re-entering in step 3).
2. Read `AgentsHub.tsx` and `apps/web/src/lib/agents.ts`'s `WIRED_AGENTS` list first — a journey is likely a new page type that sequences existing agent pages/handlers rather than a backend graph change, which keeps the blast radius small.
3. Backend-side, LangGraph already supports sub-graph composition; a "journey" could plausibly become a top-level graph that dispatches to the existing per-agent graphs as nodes — but this is a real architecture decision (state-shape unification across agents with different `TypedDict`s) and should go through an explicit design pass, not be improvised mid-implementation.
4. Start with the UX layer (a linear stepper UI hopping between existing agent pages, carrying a few shared fields via query params or session storage) before attempting true backend graph composition — much lower risk, validates demand first.

### 6. Location-based hazard alerts

An opt-in "alerts for your district" feature — air quality (API/haze readings), water disruption notices, weather advisories from JPS/DOE — extending the existing Warung Watch real-time-data pattern into official hazard data: same technical pattern, different (and higher-trust) data source.

**Why it fits:** Warung Watch (`apps/web/src/app/warung-watch/`, migrations 032/033) already proves the "live, location-scoped, periodically-refreshed data" pattern works in this codebase. This is the same shape applied to a civic-safety data source instead of retail prices.

**How an AI agent could explore this:**
1. Read `apps/web/src/app/warung-watch/page.tsx`, `WarungPriceChart.tsx`, and migrations 032/033 first — these are the concrete precedent for "opt-in, location-scoped, periodically-refreshed" features in this repo, and should be followed for API shape and refresh cadence rather than designed from scratch.
2. Data source verification is the real blocker here, not code: confirm live, genuinely official API/haze and water-disruption feeds exist per state/district (JPS, DOE) before any schema work — per `scripts/sources.py`'s own rule, no guessed feed URLs.
3. "Opt-in" and "your district" imply a location preference stored per user — check whether user profile/preferences already have a place for this (`services/auth.py`, profile page) before adding a new table.
4. This is the one idea in this document that plausibly needs push notifications or at least a "check on load" pattern distinct from RAG/chat — scope that delivery mechanism explicitly before starting, since it's a different engineering surface (background jobs / webhooks) than anything else in the agent-pipeline codebase today.

---

## Cross-cutting notes for whoever picks these up

- **None of these are scoped for immediate implementation.** Each "how an AI agent could explore this" section is a starting point for a proper plan (read the cited files, verify data sources are real, make the architecture calls explicitly), not a spec to execute blind.
- **Domain-list and i18n discipline apply to all of them** — any new domain, agent, or UI string follows the same Trap #6 / Trap #10 rules as existing code.
- **Trust USP is the tie-breaker** for any ambiguous scope call across all six ideas: when a feature could either surface official, cited information *or* take a shortcut (approximate a rate, guess a URL, invent a procedural requirement), the cited/verified path wins even if it ships less.
