import { bundle } from "@remotion/bundler";
import { renderMedia, selectComposition } from "@remotion/renderer";
import path from "node:path";

// Remotion's own headless-shell download is blocked in some sandboxes; point at any local Chromium.
const browserExecutable = process.env.CHROMIUM_PATH ?? null;
const ids = process.argv.slice(2);
const serveUrl = await bundle({ entryPoint: path.resolve("src/index.ts") });
for (const id of ids) {
  const composition = await selectComposition({ serveUrl, id, browserExecutable });
  const out = `out/naktahu-${id.toLowerCase()}.mp4`;
  const t0 = Date.now();
  await renderMedia({ serveUrl, composition, codec: "h264", crf: 17, outputLocation: out, browserExecutable, concurrency: 4 });
  console.log(`${id} -> ${out} in ${Math.round((Date.now() - t0) / 1000)}s`);
}
