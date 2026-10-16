# Hackathon submission: audit, demo script, draft text

Working notes, not product docs. Status key: DONE = verified in the repo or on GitHub;
BLOCKER = must be done by you before submitting; CHECK = I could not verify from here.

## 1. Checklist audit

| Requirement | Status | What is true today |
|---|---|---|
| Project built with Nemotron on Token Factory | **BLOCKER** | The code exists (`apps/api/app/agents/eligibility_agent/llm_split.py`, flag-gated) but has never been run against Token Factory. Model IDs are deliberately not defaulted. Run `python scripts/nemotron_check.py` with your key and candidate IDs, fix the IDs from the catalog it prints, then set `ELIGIBILITY_USE_NEMOTRON=true`, `NEMOTRON_API_KEY`, `NEMOTRON_FAST_MODEL`, `NEMOTRON_REASONING_MODEL` on Railway. |
| Category / track | **CHECK** | You pick it from the track page. I do not know the track list; Grant Agent (an enterprise/SME agent) is the natural fit. |
| Project description | Draft below | Needs your final wording. |
| Working demo URL | **CHECK** | `https://naktahu.my` is set as the repo homepage. Confirm Grant Finder works there with Nemotron on, signed out or with a judge-usable login, and that rate limits will not block judges. |
| Demo video, 3 min, public YouTube | **BLOCKER** | Script below. It must visibly show Nemotron on Token Factory (see section 2, risk 1). |
| Public repo | DONE | `timothylee58/naktahu-AI` is public. |
| Open-source licence visible at top | DONE | GitHub detects Apache-2.0 from `LICENSE`. |
| README with setup and run guidance | Partly | Setup, env table and Nemotron env vars are there. It has no dedicated section that says how Nemotron and Token Factory are used and what they sped up. Add one after the facts exist (after the first live run). |
| Highlight other Nebius tools | **CHECK** | Only Token Factory is wired (and unrun). The Nebius Serverless Jobs runner in `scripts/evals/faithfulness/nebius/` is written but never built or run, so do not claim it unless you run it. |
| Feedback on Nebius / NVIDIA tools | **BLOCKER** | Only you can write it. Prompts in section 5. |
| "What was updated in the submission period" | **CHECK** | `README.md` has a "What's new (October 2026)" list. Tell me the period's start date and I will cut it to just that window. The repo itself dates from April 2026; the Nemotron split merged on 2026-10-09 (PR #240). |

## 2. Risks to fix before recording

1. **The UI cannot show which model answered.** The API sends `llm_provider` (`nemotron`, `ilmu` or Claude) in the metadata event, but nothing in `apps/web` reads it. If Nemotron fails before its first token the agent silently falls back to ILMU, so a recording could look like Nemotron while ILMU is answering. Fix: a small "Answered by" badge in Grant Finder from `llm_provider`. Until then, prove it on screen with the Token Factory console or API logs.
2. **Intake with the fast model is unmeasured.** The BM/EN/ZH intake eval (`RUN_LIVE_EVALS=1`) has never been run. Run it once with Nemotron on; if Mandarin is below 0.85, rehearse the demo in a language that works, and say so honestly.
3. **Fast model ID unknown.** `NEMOTRON_FAST_MODEL` is "a Nano-class model", still unconfirmed against your account's catalog.
4. **Reasoning models think out loud.** Output is stripped of `<think>` blocks, and the first token can take up to 60 s. Do a warm run before recording and cut the wait in editing.
5. **Do not demo the faithfulness gate as passing.** It reads `NOT MEASURED`. Say "built, calibration pending" or leave it out.
6. **Tavily key.** Without `TAVILY_API_KEY` the stamps show `unavailable`. Set it before recording, and expect `no_signal` for agencies whose pages state no date; that is correct behaviour, not a bug.
7. Tax-incentive matching (Pioneer Status, ITA, RA) is deliberately unbuilt. Do not promise it.

## 3. Demo script (target 2:50)

Record in Mandarin or whichever language scores best in risk 2. Keep the rest of the UI in English so judges can read it.

| Time | Screen | Say |
|---|---|---|
| 0:00-0:15 | Title card, then Grant Finder landing | "Malaysian SMEs miss grants because the information is scattered across a dozen agencies and the deadlines keep moving. NakTahu's Grant Finder answers one question: what can my business apply for, right now?" |
| 0:15-0:45 | Type the business description in Mandarin (a Sdn Bhd tech firm, about RM500k revenue, 12 staff, not Bumiputera) | "I describe my business in plain Mandarin. A small Nemotron model on Nebius Token Factory pulls out the structured profile: business type, sector, revenue, headcount." Show the extracted fields. |
| 0:45-1:30 | Results: matched grants, near-misses, stacking matrix | "Which grants match is decided by deterministic code, not the model, so it cannot invent an eligibility. Near-misses show what is one step away. The stacking matrix shows which programmes can be combined." |
| 1:30-1:55 | Open one grant: required-documents checklist | "For each grant, the exact documents to prepare." |
| 1:55-2:20 | Point at the last-verified stamps | "Deadlines go stale. Each top match is re-checked live against the agency's own website through Tavily, restricted to that agency's domain, and stamped confirmed, changed, closed or unverified. We never silently pass an unchecked grant." |
| 2:20-2:40 | Token Factory console or API log with the model ID and request; the "Answered by" badge if built | "The summary you just watched stream was written by Nemotron's reasoning model on Token Factory. If it fails, the agent falls back to our primary provider, so users are never left without an answer." |
| 2:40-2:50 | GitHub repo page showing Apache-2.0, then the CI checks | "Open source under Apache 2.0, with evals in CI. Repo link below." |

Pre-flight: warm the model once; use a fresh anonymous session; hide API keys and the Railway/Supabase dashboards; keep the Token Factory tab already open on the right project; do not show the faithfulness gate or Serverless Jobs unless you have run them.

## 4. Draft project description (edit freely)

**What it is.** NakTahu Grant Finder is a bilingual-plus (BM, EN, Mandarin) agent that tells a Malaysian SME which government grants it can apply for, which can be stacked, and which documents to prepare.

**Why.** Grant information is spread across many agencies, in different languages, and intake windows change without notice. Owners either miss grants or lose weeks working out eligibility.

**How it works.** A short conversation builds a business profile. A Nemotron fast model on Nebius Token Factory extracts the structured fields; matching, near-miss detection and stacking are deterministic and tested, so the model never decides eligibility. The top matches are re-verified live against each agency's own page (Tavily) and shown with a last-verified stamp. A Nemotron reasoning model streams a plain-language summary, with automatic fallback to the primary provider. [Fill in only after the first live run: measured latency or quality numbers.]

**Honest limits.** Statutory tax-incentive matching is not built. The faithfulness judge and the trilingual intake eval are written but not yet calibrated against live models.

## 5. Feedback prompts (you write it; be specific)

- Token Factory: time from signup to first successful call; whether the model catalog and IDs were easy to find; how `nemotron_check.py`-style listing behaved; rate limits or errors hit.
- Nemotron: how the fast model handled Malay and Mandarin extraction; how long the reasoning model took to its first token; any trouble with `<think>` output or `extra_body` switches.
- Docs and tooling: anything you had to guess; anything that saved time.
- Nebius AI Cloud / Serverless Jobs, if you try it: image build and job submission experience.
