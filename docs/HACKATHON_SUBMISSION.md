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
| Demo video, 3 min, public YouTube | **BLOCKER** | Script below. It shows Nemotron through the SSE endpoint, because the web form does not call it (section 2, risk 1). |
| Public repo | DONE | `timothylee58/naktahu-AI` is public. |
| Open-source licence visible at top | DONE | GitHub detects Apache-2.0 from `LICENSE`. |
| README with setup and run guidance | Partly | Setup, env table and Nemotron env vars are there. It has no dedicated section that says how Nemotron and Token Factory are used and what they sped up. Add one after the facts exist (after the first live run). |
| Highlight other Nebius tools | **CHECK** | Only Token Factory is wired (and unrun). The Nebius Serverless Jobs runner in `scripts/evals/faithfulness/nebius/` is written but never built or run, so do not claim it unless you run it. |
| Feedback on Nebius / NVIDIA tools | **BLOCKER** | Only you can write it. Prompts in section 5. |
| "What was updated in the submission period" | **CHECK** | `README.md` has a "What's new (October 2026)" list. Tell me the period's start date and I will cut it to just that window. The repo itself dates from April 2026; the Nemotron split merged on 2026-10-09 (PR #240). |

## 2. Risks to fix before recording

1. **The web Grant Finder never calls the reasoning model.** The page is a form (chips and number fields) that calls the generic agents endpoint, which runs intake, retrieval, scoring and verification but not the summary writer. The Nemotron reasoning model runs only in the SSE endpoints (`/api/v1/eligibility/start` and `/message`), which no page in `apps/web` calls. The fast model runs only when a user types a free-text reply in the chat step. So a screen recording of the form flow shows no Nemotron at all. Decision taken: leave the UI alone, and show Nemotron through the SSE endpoint plus the Token Factory console (demo script below). The API's `llm_provider` field in the final `metadata` event is the proof of which model answered, including a silent fallback to ILMU.
2. **Intake with the fast model is unmeasured.** The BM/EN/ZH intake eval (`RUN_LIVE_EVALS=1`) has never been run. Run it once with Nemotron on; if Mandarin is below 0.85, rehearse the demo in a language that works, and say so honestly.
3. **Fast model ID unknown.** `NEMOTRON_FAST_MODEL` is "a Nano-class model", still unconfirmed against your account's catalog.
4. **Reasoning models think out loud.** Output is stripped of `<think>` blocks, and the first token can take up to 60 s. Do a warm run before recording and cut the wait in editing.
5. **Do not demo the faithfulness gate as passing.** It reads `NOT MEASURED`. Say "built, calibration pending" or leave it out.
6. **Tavily key.** Without `TAVILY_API_KEY` the stamps show `unavailable`. Set it before recording, and expect `no_signal` for agencies whose pages state no date; that is correct behaviour, not a bug.
7. Tax-incentive matching (Pioneer Status, ITA, RA) is deliberately unbuilt. Do not promise it.

## 3. Demo script (target 2:50)

The web form does not call Nemotron (risk 1), so the demo has two halves: the web UI for what users see, and a terminal for the Nemotron path. Use the SSE endpoint with `curl -N` (or a saved script) against the deployed API. Write the script in advance, send each turn in Mandarin, and test the exact commands before recording: the `/message` request shape is in `apps/api/app/routers/eligibility.py`.

| Time | Screen | Say |
|---|---|---|
| 0:00-0:15 | Title card, then Grant Finder form | "Malaysian SMEs miss grants because the information is scattered across a dozen agencies and the deadlines keep moving. NakTahu's Grant Finder answers one question: what can my business apply for, right now?" |
| 0:15-0:50 | Web form: pick sector, business type, revenue, Bumiputera status; submit | "The matching is deterministic code, not a model, so it cannot invent an eligibility." Show matched grants, near-misses and the stacking matrix. |
| 0:50-1:15 | Open one grant: documents checklist and the last-verified stamp | "For each grant, the exact documents to prepare. Deadlines go stale, so each top match is re-checked live against the agency's own website through Tavily, restricted to that agency's domain, and stamped confirmed, changed, closed or unverified." |
| 1:15-2:20 | Terminal: `curl -N` to `/api/v1/eligibility/start`, then `/message` turns in Mandarin describing the business | "The same agent also takes a plain-language conversation. A small Nemotron model on Nebius Token Factory pulls the structured profile out of my Mandarin answers. Once the profile is complete, Nemotron's reasoning model streams a plain-language summary." Let the tokens stream. |
| 2:20-2:40 | The final `metadata` event showing `"llm_provider": "nemotron"`, then the Token Factory console with the request | "The API reports which model answered. If Nemotron fails, the agent falls back to our primary provider, and this field would say so." |
| 2:40-2:50 | GitHub repo page showing Apache-2.0, then the CI checks | "Open source under Apache 2.0, with evals in CI. Repo link below." |

Pre-flight: warm the model once (the first token can take up to 60 s; cut the wait in editing); use an anonymous session; hide API keys and the Railway/Supabase dashboards; keep the Token Factory tab open on the right project; do not show the faithfulness gate or Serverless Jobs unless you have run them. If `llm_provider` reads `ilmu`, Nemotron is not configured: fix that before recording.

## 4. Draft project description (edit freely)

**What it is.** NakTahu Grant Finder is a bilingual-plus (BM, EN, Mandarin) agent that tells a Malaysian SME which government grants it can apply for, which can be stacked, and which documents to prepare.

**Why.** Grant information is spread across many agencies, in different languages, and intake windows change without notice. Owners either miss grants or lose weeks working out eligibility.

**How it works.** A short conversation builds a business profile. A Nemotron fast model on Nebius Token Factory extracts the structured fields; matching, near-miss detection and stacking are deterministic and tested, so the model never decides eligibility. The top matches are re-verified live against each agency's own page (Tavily) and shown with a last-verified stamp. In the conversational API (`/api/v1/eligibility`), a Nemotron reasoning model streams a plain-language summary, with automatic fallback to the primary provider; the web form flow shows the deterministic results only. [Fill in only after the first live run: measured latency or quality numbers.]

**Honest limits.** Statutory tax-incentive matching is not built. The faithfulness judge and the trilingual intake eval are written but not yet calibrated against live models.

## 5. Feedback prompts (you write it; be specific)

- Token Factory: time from signup to first successful call; whether the model catalog and IDs were easy to find; how `nemotron_check.py`-style listing behaved; rate limits or errors hit.
- Nemotron: how the fast model handled Malay and Mandarin extraction; how long the reasoning model took to its first token; any trouble with `<think>` output or `extra_body` switches.
- Docs and tooling: anything you had to guess; anything that saved time.
- Nebius AI Cloud / Serverless Jobs, if you try it: image build and job submission experience.
