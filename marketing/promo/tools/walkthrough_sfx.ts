/**
 * Emit the UI sound cues for one walkthrough, straight from its script:
 * a click on every cursor click, a whoosh into every chapter card, a pop as
 * each callout lands. Keeps the score in sync when a script is re-timed.
 *
 *   npx tsx tools/walkthrough_sfx.ts ask > audio/walkthrough_ask.sfx.json
 */
import { WALKTHROUGHS } from "../src/Walkthrough/scripts";
import { CH0, CH_DUR, RECAP, TITLE } from "../src/Walkthrough/timeline";

const s = WALKTHROUGHS.find((w) => w.id === process.argv[2]);
if (!s) throw new Error(`unknown walkthrough ${process.argv[2]}`);
const ev: Record<string, unknown>[] = [{ kind: "whoosh", frame: TITLE.from - 8, sec: 0.5 }];
s.chapters.forEach((c, i) => {
  const t0 = CH0 + i * CH_DUR;
  ev.push({ kind: "whoosh", frame: t0 - 6, sec: 0.35 });
  for (const k of c.cursor ?? []) if (k.click) ev.push({ kind: "click", frame: t0 + k.f });
  for (const k of c.callouts ?? []) ev.push({ kind: "pop", frame: t0 + k.f + 2, gain: 0.7 });
});
ev.push({ kind: "whoosh", frame: RECAP.from - 6, sec: 0.4 }, { kind: "bell", frame: RECAP.from + 80, note: 84 });
console.log(JSON.stringify(ev));
// the font loaders in the imported UI reject once outside a browser; the cues are already out
process.exit(0);
