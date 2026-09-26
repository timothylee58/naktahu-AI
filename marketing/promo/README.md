# naktahu.my marketing videos

Remotion source for the naktahu.my promo videos. This is a standalone package: it is not an npm workspace and it is not part of the web build or CI.

| Composition | Length | What it is |
|---|---|---|
| `NaktahuPromo` | 20s, 16:9 | Brand promo (BM) |
| `Showcase-{bm,en,zh}-16x9` | 38s | Feature showcase, landscape |
| `Showcase-{bm,en,zh}-9x16` | 38s | Feature showcase, vertical (Reels / TikTok / Shorts) |

The showcase is cut to a 128.57 BPM track, which is exactly 14 frames per beat at 30fps, so every scene change lands on a beat. Bar `n` starts at frame `n * 56`.

## Render

```bash
npm install

# 1. Generate the audio. The WAVs are build outputs and are not committed.
python3 audio/score_promo20.py                  # stdlib only -> public/score.wav
pip install numpy scipy
python3 audio/score_showcase.py audio/showcase_sfx.json public/showcase.wav

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
