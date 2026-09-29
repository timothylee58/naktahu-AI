# naktahu.my marketing videos

Remotion source for the naktahu.my promo videos. This is a standalone package: it is not an npm workspace and it is not part of the web build or CI.

| Composition | Length | What it is |
|---|---|---|
| `NaktahuPromo` | 20s, 16:9 | Brand promo (BM) |
| `Showcase-{bm,en,zh}-16x9` | 56.5s | Feature showcase, landscape |
| `Showcase-{bm,en,zh}-9x16` | 56.5s | Feature showcase, vertical (Reels / TikTok / Shorts) |
| `Walkthrough-ask` | 100s, 16:9 | Walkthrough 01 — Ask anything: question → cited answer → BM/中文 + voice → share → follow-ups |
| `Walkthrough-business` | 100s, 16:9 | Walkthrough 02 — Run your business: agents hub → Grant Finder → Grant Draft → PatuhiKu → Deadline Monitor |
| `Walkthrough-life` | 100s, 16:9 | Walkthrough 03 — Life moments: Health Triage → Immigration → Check Assistance → Retrenchment → Study Agent |

Each scene is one 84-frame bar (2.8s). The showcase score (`audio/score_parkbench.py`) is the "Park Bench" boom-bap beat, Fm7 → Dbmaj7 → Bbm7 → C7alt, at 85.71 BPM, which is exactly 21 frames per beat. That puts every scene change on beat 1. Earlier scores are kept in `audio/` for reference.

The walkthroughs (`src/Walkthrough/`) film a rebuilt app shell with a virtual camera (`engine.tsx`: camera keys, cursor, callouts, spotlight, captions). Each video is a script (`ask.tsx`, `business.tsx`, `life.tsx`) on a fixed timeline (`timeline.ts`): hook, title, five 6-bar chapters, recap, end card, at 90 BPM (20 frames per beat). UI labels are the product's real EN strings; grant, deadline and scheme results are illustrative and carry an on-screen "illustrative demo data" flag.

## Render

```bash
npm install

# 1. Generate the audio. The WAVs are build outputs and are not committed.
python3 audio/score_promo20.py                  # stdlib only -> public/score.wav
pip install numpy scipy
python3 audio/score_parkbench.py audio/showcase_sfx.json public/showcase.wav
for w in ask business life; do   # walkthroughs: click/whoosh cues come from each script
  npx tsx tools/walkthrough_sfx.ts $w > /tmp/$w.sfx.json
  python3 audio/score_walkthrough.py audio/walkthrough_$w.json public/wt-$w.wav /tmp/$w.sfx.json
done

# 2. Preview, or render
npx remotion studio
node render.mjs Showcase-en-16x9 Showcase-zh-9x16   # -> out/*.mp4
```

If Remotion cannot download its headless Chromium (for example behind a proxy), set `CHROMIUM_PATH` to a local Chromium or headless_shell binary.

## Editing copy

All on-screen text lives in `src/Showcase/copy.{bm,en,zh}.ts`.

- **BM is the source.** Wherever a string exists in the product, it is the product's own wording from `apps/web/src/lib/i18n/index.tsx` or `TypewriterQuery.tsx`. The `// i18n:<key>` comment marks each such string.
- **Keep the videos in step with the product.** If you change product copy, update the matching key here too.

After changing any Chinese text, rebuild the Chinese font subset:

```bash
cat src/**/*.ts* src/*.tsx > /tmp/text.txt
npm i --no-save @fontsource/noto-sans-sc
python3 tools/subset_cjk.py node_modules/@fontsource/noto-sans-sc /tmp/text.txt public/fonts   # needs fonttools + brotli
```

## Licences

- **Fonts:** Plus Jakarta Sans, IBM Plex Mono and Noto Sans SC (subset) are distributed under the SIL Open Font License (`public/fonts/OFL.txt`).
- **Music and sound effects:** original, synthesised by the scripts in `audio/`. No samples or third-party audio are used.
