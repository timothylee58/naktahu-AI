# Ingesting numeric economic time-series and statistical releases into a RAG knowledge base (Postgres/pgvector hybrid, Malaysian finance Q&A)

Method note: 8 searches, 1 fetch (bnm.gov.my fetch failed: host not in the session's allowed network domains, so BNM pages were not read directly). Search outputs were summaries of results, not full-page reads, so most findings below are from snippets/abstracts and are flagged accordingly. Much of the "best practice" literature is practitioner blogs and preprints; strong, replicated evidence for time-series-specific RAG chunking is thin.

## 1. How to chunk and phrase time series (per-observation vs per-period vs latest-value cards)

### Takeaway
Evidence favours self-contained, context-bearing chunks (series name, unit, period, as-of date, source in the text) and grouping rows into logical blocks (period windows) rather than isolated rows; aggregations and "latest value" lookups are better served by structured queries/cards than by retrieving many rows. No source tested per-observation vs summary vs latest-card designs head to head, so the specific design below is an inference.

### Cited Findings
- Chunks should carry headings, table headers, source identifiers, timestamps and access metadata, because a semantically similar fragment is useless if parsing dropped the context the answer needs; build a chunking eval set and test tables separately from prose — [Oracle](https://blogs.oracle.com/developers/rag-chunking-and-parsing-for-tables-pdfs-transcripts-and-media), [Oracle (alt)](https://blogs.oracle.com/developers/?p=5828)
- Row-only chunks lose meaning (a revenue figure cannot be tied to company/period without the table's labels); small self-contained tables can be kept whole; serializing rows as key-value/JSON text is another option — [hyper.ai summary](https://hyper.ai/en/stories/773bdcce392482c11740265d0fb3c9fc) (secondary aggregator, weak)
- Repeat column headers in each table chunk and include workbook/sheet/section names; store structured fields for numeric filtering via SQL — [Oracle](https://blogs.oracle.com/developers/?p=5828)
- For time series/crosstabs, split into logical blocks such as periods; one guide suggests grouping about 3-10 rows by shared attribute such as time window — [Towards AI](https://pub.towardsai.net/rag-chunking-techniques-for-tabular-data-10-powerful-strategies-aba887de331e), [HackerNoon](https://hackernoon.com/chunking-strategies-for-structured-data-in-rag-systems) (practitioner blogs, weak)
- Aggregations (averages, "which was highest") need the whole table; partial chunks cannot support them. Route lookups to RAG and aggregations to text-to-SQL — [UNU TableMind](https://c3.unu.edu/projects/ai/tablemind/blog_article.html), [HackerNoon](https://hackernoon.com/chunking-strategies-for-structured-data-in-rag-systems)
- Multi-page tables are a known failure for page-boundary chunking — [LangChain](https://www.langchain.com/blog/benchmarking-rag-on-tables)
- An arXiv paper (2605.00318) reports structure-aware chunking improves retrieval over CSV/Excel data; only the abstract was seen, benchmarks unverified — [arXiv](https://arxiv.org/abs/2605.00318)

### Inferences
- Suggested three chunk types for BNM-style data (my design, not source-tested):
  1. Latest-value card per series: one chunk, e.g. "Overnight Policy Rate (OPR), Bank Negara Malaysia: 2.75% per annum, effective/as of <date>; previous 3.00% (changed <date>). Source: <series URL>". Replaced in place on update.
  2. Change-event chunks for step series (OPR changes only, each MPC decision date with old to new rate and a link to the statement). OPR changes rarely, so per-event chunks are tiny in number and answer "when did OPR change / what was it in <month>" well.
  3. Per-period summary chunks for dense series (daily FX): one chunk per currency pair per month (open/close/high/low/mean, units "MYR per 1 USD", date range, count of observations), optionally a small table of the days for that month (~20-23 rows). A per-month chunk can answer "USD/MYR last March" without 20+ near-identical per-day chunks.
- Per-observation chunks for daily series are the highest-risk design for near-duplicate flooding (see section 2); keep full daily history in a relational table and expose it via a structured lookup/SQL tool rather than embeddings.
- Put the natural-language month/year words ("March 2026", "Mac 2026") and series aliases (OPR, kadar dasar semalaman, USD/MYR, ringgit) in chunk text so BM25/keyword side matches bilingual queries; the embedding side alone is weak at exact dates/numbers.

### Gaps
- No source compared per-observation vs per-period vs latest-card designs on retrieval accuracy for time series. No benchmark found specific to central-bank statistics.
- Bilingual (BM/EN) phrasing guidance for numeric chunks: nothing found.

## 2. Freshness, supersession, as-of dates, dedupe, avoiding index flooding

### Takeaway
Standard dense retrieval cannot tell a fact's old and new versions apart, so time must be an explicit field in the index/scoring, not left to embeddings. Near-duplicates waste top-k slots and reduce diversity; dedupe by hash and diversify (MMR), but measured accuracy gains depend on how redundant the corpus is.

### Cited Findings
- Temporal-RAG papers share a thread: retrieval needs a time signal in the index, scoring or query; same fact at different times is hard to distinguish with vector embeddings — [RAG Meets Temporal Graphs](https://arxiv.org/pdf/2510.13590), [Solving Freshness in RAG (recency prior)](https://arxiv.org/html/2509.19376v1), [Re3, ACL 2026](https://aclanthology.org/2026.acl-long.1180.pdf), [VersionRAG](https://arxiv.org/pdf/2510.08109), [Chronofy](https://arxiv.org/pdf/2607.20560) (preprints; benchmark claims not checked)
- A recency-weighted layer can serve both "latest" and explicit "as-of" queries (as-of answered against a time-bounded snapshot) — [Solving Freshness in RAG](https://arxiv.org/html/2509.19376v1)
- Near-duplicates degrade retrieval accuracy and diversity (MS MARCO V2 finding) — [Ragnarok / TREC 2024 RAG](https://arxiv.org/pdf/2406.16828); top-k over duplicated entries returns multiple copies of one passage — [Byte-Exact Deduplication](https://arxiv.org/pdf/2605.09611)
- Duplicates arise from overlapping chunks, repeated boilerplate and duplicate source docs; redundancy wastes context and distracts the generator — [Reducing Redundancy via Chunk Filtering](https://arxiv.org/pdf/2604.24334)
- MMR and variants are widely used; a similarity-threshold filter removed 20.5% of chunks at 0.5 and 8.5% at 0.9 — [Chunk Filtering](https://arxiv.org/pdf/2604.24334)
- Counter-evidence on benefit: a student project (SimHash/MinHash/SBERT) removed ~2-4% near-duplicates with minimal or slightly positive effect on accuracy; exact-dedup preprint reports no measurable quality regression, not a gain — [CS6101 project](https://wing-nus.github.io/cs6101/files/STePS-2025/CS6101-04.pdf), [Byte-Exact Dedup](https://arxiv.org/abs/2605.09611) (weak: student project)

### Inferences
- Recommended metadata per chunk (jsonb on `document_chunks`, plus indexed columns where filtered): `series_id`, `as_of_date` (date value applies), `observation_period`, `fetched_at`, `unit` (e.g. "% p.a.", "MYR per 1 USD"), `source_url` (exact series/dataset URL, never constructed), `is_current` (bool), `superseded_by`/`valid_to`, `content_hash`.
- Supersession: latest-value cards upsert on `(series_id, 'latest')` and move the prior value into a change-event chunk; mark old rows `is_current=false` and filter them from default search (keep for explicit historical queries) rather than leaving both live. Historical per-period chunks are immutable once the period closes (except for BNM revisions; re-hash and replace).
- content_hash must hash the normalized value text including the as-of date, so an unchanged daily refetch is a no-op (no new row) and a revised value yields a new row plus supersession of the old.
- Add an in-pipeline "latest" intent: if the query has no date, filter `is_current` and boost recency; if it names a date/month, filter by `as_of_date` range (hybrid search plus SQL predicate) rather than trusting the embedding to pick the month.
- Keep daily FX as structured rows and ingest at most per-month summaries and one latest card per pair into the vector index; this limits near-duplicates by construction.
- Embeddings (1536-dim text-embedding-3-small) separate "0.3 vs 0.30" and months poorly (my inference from general embedding behaviour; no source found). Do not rely on vector similarity to match numbers/dates.

### Gaps
- No source on supersession patterns specific to pgvector; design above is inference.
- No quantitative evidence on how many near-duplicate numeric rows begin to hurt ranking on a corpus of this size.

## 3. Numeric RAG pitfalls: table misreading, unit/period confusion, stale cache, citing the exact series URL

### Takeaway
The main documented failure modes are wrong row/column/period selection, unit/scale errors and LLM arithmetic mistakes; mitigations are deterministic computation and verification against source values. Stale-cache and citation-URL handling are not covered by the sources found and rest on repo rules plus inference.

### Cited Findings
- Intrinsic hallucination in financial table QA (output contradicting the provided table); FAITH paper estimates 10-20% hallucination rates in complex financial reasoning can have outsized impact (estimate, preprint) — [FAITH](https://arxiv.org/html/2508.05201)
- "Numeric Neighbor Traps" (picking an adjacent temporal column) and LLM arithmetic weakness; proposed fix of LLM-generated deterministic Python reported ~1.2% hallucination (authors' own, unverified) — VeNRA preprint as surfaced via search; see also [Confidently Wrong](https://arxiv.org/pdf/2607.11414) for related financial-QA hallucination work (exact VeNRA URL not captured, treat as weak)
- Unit/scale mismatches (mostly thousands) affect a small share of answers: ~0.9-1.4% on FinQA, 2.9-5.1% on TAT-QA — [Confidently Wrong](https://arxiv.org/pdf/2607.11414)
- T2-RAGBench: requires retrieving the right context before numerical reasoning over text+tables — [T2-RAGBench](https://arxiv.org/html/2506.12071v1)
- BNM publishes rates and statistics through an Open API as well as website and CSV downloads (2019 announcement; other statistics to follow); developer portal name `apikijangportal.bnm.gov.my` appears only in a third-party listing and is unverified; third-party wrappers (Zyla, Apify) serve OPR but are not official — [BNM Open API](https://www.bnm.gov.my/-/bnm-openapi) (from search snippet only; page fetch failed), [Apify BNM scraper](https://apify.com/jungle_synthesizer/bank-negara-malaysia-fx-rate-economy-scraper)
- data.gov.my carries BNM-derived catalogues (exchange rates, monthly interest rates) — [data.gov.my exchange rates](https://data.gov.my/data-catalogue/exchangerates), [Monthly Interest Rates](https://data.gov.my/data-catalogue/interestrates)

### Inferences
- Put unit and period in the chunk's first sentence and as metadata; have the synthesiser restate "as of <date>, in % p.a." and refuse to answer a dated question if no chunk's `as_of_date` covers it (feeds the existing `needs_clarification` trust path).
- Do arithmetic (change vs last month, percent change, averages) in code over structured rows, not in the LLM.
- Query-result cache (3600s TTL) can serve an OPR answer after an MPC decision changes it. Suggested: invalidate/bypass cache keys for the `finance` domain when a series card is superseded (e.g. store a `corpus_version`/series update stamp in the cache key or flush on ingest), since the hash key excludes data freshness. This is my inference from the repo rules, not from a source.
- Citation: store the exact dataset/series page URL (from the API/catalogue, or the MPC statement URL) in chunk metadata and emit only that; a bare bnm.gov.my homepage is not an acceptable citation. If the API endpoint requires a key, cite the human-readable page, not the API URL.

### Gaps
- No source on stale-cache invalidation for RAG answers.
- Could not read BNM pages (network block): API licensing/attribution terms, endpoint list, rate limits and whether an OPR endpoint exists are unverified.
- VeNRA primary URL not captured.

## 4. Prompt-injection risk when ingesting third-party text; controls vs trusted structured numbers

### Takeaway
Corpus poisoning is real and current defenses only partially mitigate it, so the safest design is to separate trusted structured API numbers (rendered by your own template, no free text) from third-party prose (scan, quarantine, review). A scan is a filter, not a guarantee.

### Cited Findings
- PoisonedRAG (USENIX Security 2025): ~90% attack success with five malicious texts per target question in a knowledge base of millions of texts; tested defenses were insufficient — [PoisonedRAG](https://usenix.org/system/files/usenixsecurity25-zou-poisonedrag.pdf)
- Later results are mixed: one follow-up reports knowledge expansion cutting ASR to 1% and black-box PoisonedRAG from 0.69 to 0.14 under a defense (setup-specific); another benchmark finds hybrid defenses best but only partial mitigation — [Benchmarking Poisoning Attacks](https://arxiv.org/html/2505.18543v1), [Attention-Aware Defenses](https://arxiv.org/pdf/2506.04390)
- A newer single-document attack reports narrative framing that survives paraphrase sanitization — [Logic Hijacking of RAG](https://arxiv.org/pdf/2610.34829) (preprint, unverified)
- Layered defenses (input filtering, prompt hardening, output monitoring) are the common direction — [Layered Security Framework for RAG Chatbots](https://arxiv.org/pdf/2606.19660) (preprint)

### Inferences
- Trust tiers: (A) numbers pulled from the official BNM/data.gov.my API and rendered by a fixed template (no free-text fields ingested) are low injection risk; still validate type/range (e.g. rate 0-20, FX > 0). (B) MPC statements, press releases, RSS prose are third-party text: run the repo's mandatory `_fold_confusables(NFKC(text))` vs `INJECTION_PATTERNS` scan, quarantine on hit (store with `status=quarantined`, excluded from search), and spot-check by human before release for new feeds.
- Never put API free-text fields (descriptions, notes) into chunk text unscanned; they pass the same scan.
- Source allowlist by domain (`bnm.gov.my`, `data.gov.my`) as an additional gate; reject chunks whose URL host is outside it, which also protects the citation rule.
- Because defenses are partial, keep the synthesiser prompt treating retrieved text as data, and keep citations limited to metadata URLs.

### Gaps
- No evidence found on injection incidents specific to central-bank/government publications; risk for official sources is presumably low but unquantified.
- Effectiveness of regex-style scans against paraphrased/narrative attacks is weak per the cited preprints; no measure for this repo's pattern list.

## 5. Volume: how much is enough, when more data hurts

### Takeaway
No source gives a number for a numeric-statistics KB. Evidence indicates redundancy and stale versions, not size per se, degrade ranking; keep the vector index small and curated and push bulk history into structured storage.

### Cited Findings
- Near-duplicates reduce retrieval accuracy and diversity and consume context window — [Ragnarok](https://arxiv.org/pdf/2406.16828), [Chunk Filtering](https://arxiv.org/pdf/2604.24334)
- Hybrid vector+FTS fused by RRF (k=60 commonly, 50 in Supabase example) improved retrieval in one team's anecdote from ~62% to ~84% precision (single anecdote, not a benchmark) — [DEV Community RRF post](https://dev.to/lpossamai/building-hybrid-search-for-rag-combining-pgvector-and-full-text-search-with-reciprocal-rank-fusion-6nk), [Supabase hybrid search](https://supabase.com/docs/guides/ai/hybrid-search), [DigitalOcean](https://docs.digitalocean.com/products/vector-databases/postgresql/how-to/use-hybrid-search/)
- Tune hybrid search on representative queries with known relevant documents — [DigitalOcean](https://docs.digitalocean.com/products/vector-databases/postgresql/how-to/use-hybrid-search/)
- Oracle recommends an evaluation set before tuning chunk size — [Oracle](https://blogs.oracle.com/developers/rag-chunking-and-parsing-for-tables-pdfs-transcripts-and-media)

### Inferences
- Rough sizing guess (not sourced): per series, 1 latest card + one chunk per change event (OPR: dozens) + one chunk per month for dense series (a decade is ~120 chunks per pair). A few dozen series then yield low thousands of chunks, small for pgvector. The risk is quality, not scale: 30 months of similar "USD/MYR monthly summary" chunks competing for top-k for an undated query.
- Mitigations: apply a date/`is_current` predicate before ranking, cap per-series results (diversify by `series_id`) in the top-k, and add MMR or per-series limit.
- Build a small eval set (e.g. 30-50 questions: "OPR now", "OPR in Mar 2023", "USD/MYR last March", "when did OPR last change", BM and EN) and gate ingestion changes on it (repo's eval-gate fits this).

### Gaps
- No empirical threshold for when adding more rows hurts; it must be measured on the project's own eval set.
- No pgvector-specific vendor guidance on near-duplicate behaviour or HNSW recall at this scale was found.
