import { BAR, TOTAL } from "./engine";

/** Fixed 100s structure shared by every walkthrough (90 BPM: bar = 80 frames). */
export const HOOK = { from: 0, dur: 2 * BAR };
export const TITLE = { from: 2 * BAR, dur: 2 * BAR };
export const CH0 = 4 * BAR;
export const CH_DUR = 6 * BAR;
export const RECAP = { from: 34 * BAR, dur: 2 * BAR };
export const END = { from: 36 * BAR, dur: TOTAL - 36 * BAR };
