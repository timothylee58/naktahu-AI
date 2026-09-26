import { bundle } from "@remotion/bundler";
import { renderStill, selectComposition } from "@remotion/renderer";
import path from "node:path";
import fs from "node:fs";

const browserExecutable = "/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell";
const [id, prefix, ...frames] = process.argv.slice(2);
const serveUrl = await bundle({ entryPoint: path.resolve("src/index.ts") });
const composition = await selectComposition({ serveUrl, id, browserExecutable });
fs.mkdirSync("review", { recursive: true });
for (const f of frames.map(Number)) {
  await renderStill({ serveUrl, composition, frame: f, output: `review/${prefix}_${String(f).padStart(4, "0")}.jpg`, imageFormat: "jpeg", jpegQuality: 80, scale: 0.5, browserExecutable });
}
console.log("done", id, frames.length);
