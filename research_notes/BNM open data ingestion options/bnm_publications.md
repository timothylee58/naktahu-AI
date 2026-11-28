# BNM non-API published material on bnm.gov.my

NOTE ON METHOD: direct fetches of www.bnm.gov.my failed (getaddrinfo ENOTFOUND; the host is not in this session's allowed network domains). Nothing below was read from the live pages. All findings come from WebSearch result snippets (which are search-engine summaries, not full page text). Treat as unverified until re-checked with network access to www.bnm.gov.my. Whether BNM blocks automated access (robots.txt, WAF) could not be checked.

## Monetary Policy Committee statements and OPR decisions

### Takeaway
MPC statements are individual HTML pages with date-coded slugs, plus an OPR decisions table by year. 2026 has six meetings; OPR reportedly held at 2.75% through at least September 2026 (November decision not confirmed).

### Cited Findings
- Statement URL pattern is `/-/monetary-policy-statement-DDMMYYYY` (also under `/en/-/...`), e.g. 22012026, 05032026, 07052026, 09072026, 03092026, 05112026 — [search results](https://www.bnm.gov.my/-/monetary-policy-statement-05112026)
- OPR decisions listing page by year: `/monetary-stability/opr-decisions`, with a tag page `/monetary-stability/opr-decisions/-/tag/opr-2026` — [OPR decisions](https://www.bnm.gov.my/monetary-stability/opr-decisions/-/tag/opr-2026)
- 2026 meeting dates per search summary: 22 Jan, 5 Mar, 7 May, 9 Jul, 3 Sep, 5 Nov; statement released 3:00 pm after each meeting; OPR 2.75% from 22 Jan through 3 Sep — [OPR decisions](https://www.bnm.gov.my/web/guest/monetary-stability/opr-decisions)
- The 5 Nov 2026 statement says 2026 growth expected above 5%; the Sep statement cited 5.7% H1 2026 growth — [5 Nov statement](https://www.bnm.gov.my/-/monetary-policy-statement-05112026), [3 Sep statement](https://www.bnm.gov.my/-/monetary-policy-statement-03092026)

### Inferences
- Slug is predictable from the published calendar, so a change-watcher can poll the OPR decisions page (dated rows) or probe the slug on meeting days.
- Format appears to be HTML (page, not PDF); PDF attachment not verified.

### Gaps
- November 2026 OPR decision value not seen. Meeting calendar for 2027 not checked. PDF/HTML format not confirmed.

## Monthly Highlights and Statistics, Annual Report, Quarterly Bulletin, FSR, Economic and Monetary Review

### Takeaway
Publications live under `/publications` with sub-series pages; formats and exact cadence not verified, but FSR is moving to annual and print Quarterly Bulletin has ended.

### Cited Findings
- Publications hub: `/publications`; sub-pages include `/publications/fsr`, `/publications/boxarticles`, `/publications/others` — [Publications](https://www.bnm.gov.my/publications)
- FSR latest listed: Second Half 2025, dated 31 Mar 2026; BNM states it will move to an annual FSR with more frequent targeted communications; XLSX charts datapack listed; page `/publications/fsr2025h2`; press release slugs like `/-/fsr25h1-pr` — [FSR](https://www.bnm.gov.my/publications/fsr2025h2)
- Quarterly Bulletin: latest seen 4Q 2025, dated 13 Feb 2026; print edition discontinued; page `/quarterly-bulletin-2025` — [Quarterly Bulletin](https://www.bnm.gov.my/quarterly-bulletin-2025)
- Monthly Highlights & Statistics: archived edition slug `/-/monthly-highlights-statistics-in-june-2025-1`; covers banking-system balance sheet, financial markets, insurance/takaful, external sector — [Monthly Highlights](https://www.bnm.gov.my/-/monthly-highlights-statistics-in-june-2025-1)
- Annual Report 2025 exists as a publications asset entry — [Annual Report 2025](https://www.bnm.gov.my/publications/-/asset_publisher/i8h7jbNMl64I/content/%253Ca-href-ar2025-%253Ebnm-annual-report-2025%253C-a%253E)

### Inferences
- Cadence (from series names, not verified): Monthly Highlights monthly; Quarterly Bulletin quarterly; Annual Report yearly (typically Q1/Q2); FSR now annual.

### Gaps
- Economic and Monetary Review (historically bundled with the Annual Report) not found in results. PDF vs HTML vs Excel per series unconfirmed except FSR datapack XLSX. 2026 Monthly Highlights latest issue not seen.

## Policy documents, circulars, press releases, alerts, listing pages

### Takeaway
Press releases and Financial Consumer Alert (FCA) updates have individual pages; no RSS found; an Email Alert subscription exists.

### Cited Findings
- Press releases listing: `/press-releases` (yearly archives like `/press-release-2014`) — [Press releases](https://www.bnm.gov.my/press-releases)
- FCA list at `/alert` and `/fca`; update items use slugs `/-/fca-update-YYMMDD` (e.g. 251226, 030826 = 3 Aug 2026) — [FCA update](https://www.bnm.gov.my/-/fca-update-030826), [Alert](https://www.bnm.gov.my/alert)
- Footer "Email Alert" is the only subscription mechanism seen; no RSS link seen — search summary of [bnm.gov.my pages](https://www.bnm.gov.my/alert)

### Gaps
- BNM policy document listing page (URL, dated items) not retrieved. RSS/sitemap existence unverified. Ringgit-related pages not found.

## Listing pages suitable for a change-watcher

### Takeaway
Best candidates: OPR decisions table, press releases, FCA list, FSR/Quarterly Bulletin/Publications pages. Unverified.

### Inferences
- Pages with dated entries and per-item date-coded slugs (MPC statements, FCA updates, press releases) suit diffing. Check for `sitemap.xml` and robots.txt once network allows.

### Gaps
- No page structure was inspected.

## Copyright and reuse terms

### Takeaway
Terms differ by section; datasets are permissive with BNM attribution, general website content is "all rights reserved".

### Cited Findings
- General Terms of Use bar uploading copyright material without owner permission; footers say "© Bank Negara Malaysia ... All rights reserved" — [Terms of Use](https://www.bnm.gov.my/terms-of-use)
- BNM Datasets terms: free use, copying, publishing, distribution if labelled as BNM-sourced; third-party datasets fall under standard terms — [Dataset terms](https://www.bnm.gov.my/terms-of-use-bnm-datasets)
- MIFC portal: no copying/redistribution/commercial exploitation without permission — [MIFC disclaimer](https://www.bnm.gov.my/web/mifc/disclaimer)

### Inferences
- Narrative publications (MPC statements, reports) likely need permission for bulk redistribution; safest for the KB is short quotation with citation and link-back, and asking BNM for written permission for full-text ingestion. Not legal advice.

### Gaps
- Full text of terms not read; automated-access (robots.txt) policy unknown.

## Complementary sources (pointers only, not researched)
- DOSM OpenDOSM / data.gov.my API; Ministry of Finance Economic Outlook; EPF; Securities Commission Malaysia (sc.com.my).
