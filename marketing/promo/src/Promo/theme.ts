import { loadFont } from "@remotion/fonts";
import { Easing, staticFile } from "remotion";

// Vendored from Fontsource: the render browser can't reach Google Fonts here.
for (const w of ["400", "500", "600", "700", "800"]) {
  loadFont({ family: "Jakarta", url: staticFile(`fonts/jakarta-${w}.woff2`), weight: w });
}
for (const w of ["400", "500"]) {
  loadFont({ family: "PlexMono", url: staticFile(`fonts/plexmono-${w}.woff2`), weight: w });
}
// Noto Sans SC subset to exactly the Han glyphs in this project (tools/subset_cjk.py),
// so the ZH cut renders identically on any machine instead of via system fallback.
for (const w of ["500", "700", "800"]) {
  loadFont({ family: "NotoSansSCSub", url: staticFile(`fonts/notosanssc-${w}.woff2`), weight: w });
}

export const display = `Jakarta, NotoSansSCSub, sans-serif`;
export const mono = `PlexMono, NotoSansSCSub, monospace`;

export const C = {
  bg: "#060918",
  panel: "#0D1231",
  blue: "#3B5BFF",
  blueHi: "#7B91FF",
  blueDeep: "#2540C9",
  amber: "#FFB238",
  red: "#E61E25",
  white: "#F4F6FF",
  mute: "#8B93C4",
  line: "rgba(160,175,255,0.16)",
};

export const EXPO_OUT = Easing.bezier(0.16, 1, 0.3, 1);
export const EXPO_IN = Easing.bezier(0.7, 0, 0.84, 0);
export const IN_OUT = Easing.bezier(0.65, 0, 0.35, 1);

export const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
