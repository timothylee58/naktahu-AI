# BNM open data platform and OpenAPI (data.bnm.gov.my / api.bnm.gov.my)

STATUS WARNING: this research session could not reach any BNM host. data.bnm.gov.my, api.bnm.gov.my (including /portal and both robots.txt files) all failed DNS resolution ("ENOTFOUND", outside the session's allowed domains). apify.com and allratestoday.com also failed; pypi.org returned a "Client Challenge" page with no content. Only one web search returned usable snippets. Everything below marked "UNVERIFIED" comes from my prior knowledge or inference and has NO source. Re-run after allowing api.bnm.gov.my, data.bnm.gov.my and www.bnm.gov.my in the session network settings.

## 1. What is data.bnm.gov.my / BNM OpenAPI; base URLs, endpoints, example paths

### Takeaway
The only confirmed fact is that the official BNM Open API portal is api.bnm.gov.my/portal and that third parties wrap it for FX, OPR, Kijang Emas and base lending rates. Exact endpoint list and paths could not be verified.

### Cited Findings
- A third-party OpenAPI spec describes a Malaysia FX service pulling from the BNM Open API at api.bnm.gov.my, covering exchange rates, Overnight Policy Rate (OPR), Kijang Emas gold prices and per-bank base lending rates — [web search result summary](https://oanor.com/api/malaysia-fx-api/openapi.json) (vendor wrapper, not official; uses its own x-oanor-key header)
- PyPI package "openbnmapi" describes itself as an unofficial Python wrapper for BNM's Open API and links to the official portal at api.bnm.gov.my/portal — [PyPI](https://pypi.org/project/openbnmapi/0.3) (page body not retrievable; claim is from search snippet)
- BNM daily and monthly exchange-rate datasets are also republished on data.gov.my / open.dosm.gov.my (BNM compiles official rates from buy/sell quotations at set times on trading days) — [data.gov.my exchangerates](https://data.gov.my/data-catalogue/exchangerates), [daily 1200](https://data.gov.my/data-catalogue/exchangerates_daily_1200)

### Inferences
- Because data.gov.my republishes BNM exchange rates, it is a fallback ingestion source for FX if the BNM API is unusable (still check its licence).
- UNVERIFIED (prior knowledge): base URL https://api.bnm.gov.my/public/ ; endpoints I recall include /exchange-rate, /exchange-rate/{currency_code}, /opr, /kijang-emas, /base-rate, /base-rate/{bank}, /interest-rate, /interest-rate/{product}, /interbank-swap, /interest-rate/interbank (KLIBOR-like), /consumer-alert, /financial-institutions (MSB, etc.), /insurance-takaful, /msb, /fi-list. Date parameters appear as path/query forms such as /exchange-rate/USD/date/2026-11-27 and ?session=1700, ?quote=rm. Treat all as hypotheses to check against /portal.
- UNVERIFIED: required header Accept: application/vnd.BNM.API.v1+json (the user's prompt cites it; the search engine could not confirm it). Response JSON believed to be {"data": ..., "meta": {"quote": ..., "session": ..., "last_updated": ...}}.
- UNVERIFIED: data.bnm.gov.my is the newer BNM Data Portal (visual data catalogue); I could not confirm whether it exposes its own API, CSV or Excel export.

### Gaps
- Official endpoint list, example paths, auth/API-key requirement, pagination, date parameters, response schema and per-series update frequency: not verified (BNM hosts unreachable).
- KLIBOR, monetary aggregates, banking statistics, interbank series: not confirmed to exist in the API; may be only in data.bnm.gov.my or the Monthly Statistical Bulletin.

## 2. Rate limits, terms of use, licence, attribution, bulk download

### Takeaway
Nothing verified. No source retrieved for limits, licence, or export options.

### Cited Findings
- None retrieved.

### Inferences
- UNVERIFIED: BNM website terms (bnm.gov.my) generally require acknowledgement of BNM as source and restrict reproduction; read the "Terms of Use" and "Copyright" pages before ingesting into document_chunks. The CLAUDE.md rule on citations (real gov.my URLs only) is compatible with citing the API portal or dataset page.
- Polite default if limits unknown: single-threaded, cache aggressively (most series update at most daily), identify a descriptive User-Agent, back off on 429/5xx.

### Gaps
- Rate limits, licence (e.g. whether any open licence applies), attribution wording, bulk/CSV/Excel availability: unverified.

## 3. robots.txt and automated-access statements

### Takeaway
Could not be read for either host.

### Cited Findings
- None (fetch of https://api.bnm.gov.my/robots.txt and https://data.bnm.gov.my/robots.txt failed with DNS errors in this sandbox).

### Gaps
- Contents of both robots.txt files and any statement on automated access: unverified. Check manually with curl from an unrestricted network.

## 4. Most useful datasets for a Malaysian Q&A engine

### Takeaway
Based on the confirmed wrapper coverage, FX rates, OPR, Kijang Emas and base lending rates are the series most relevant and confirmed to be exposed by the BNM API.

### Cited Findings
- Confirmed (via third-party wrapper description) as sourced from BNM Open API: exchange rates, OPR, Kijang Emas prices, bank base lending rates — [oanor spec](https://oanor.com/api/malaysia-fx-api/openapi.json)

### Inferences
- Question types users ask (current OPR, USD/MYR, gold price, base rate per bank) map directly to these four; they are small, structured, and fit as time-stamped "facts" rows rather than long-form chunks (note CLAUDE.md Trap #14: anything affecting live answers must go to document_chunks with content_hash dedup and injection scan).
- UNVERIFIED candidates to check on data.bnm.gov.my: KLIBOR/interbank rates, MGS yields, monetary aggregates (M1/M3), banking system statistics, inflation/GDP cross-references (DOSM covers CPI/GDP via data.gov.my instead).

### Gaps
- Whether KLIBOR, monetary aggregates and banking statistics are available programmatically from BNM: unverified.
