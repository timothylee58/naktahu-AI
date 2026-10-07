import React from "react";
import { useCurrentFrame } from "remotion";
import { Mark } from "../Promo/Mark";
import { C, EXPO_OUT, display, mono, prog } from "./engine";
import { useW } from "./i18n";

/**
 * App-space UI kit: a faithful-in-spirit rebuild of the naktahu.my app shell
 * (sidebar rail, header, cards, fields) at 1920x1080, so the camera can film
 * it like a screen recording. Labels come from apps/web's real EN strings;
 * the kit translates string props/children through useW(), so scripts can
 * pass English and get the walkthrough's language.
 */
export const SIDEBAR_W = 300;
export const HEADER_H = 96;
export const CONTENT = { x: SIDEBAR_W + 48, y: HEADER_H + 36, w: 1920 - SIDEBAR_W - 96, h: 1080 - HEADER_H - 72 };

export const G = {
  green: "#3DDC97",
  greenSoft: "rgba(61,220,151,0.14)",
  amberSoft: "rgba(255,178,56,0.14)",
  redSoft: "rgba(230,30,37,0.16)",
  panel: "rgba(255,255,255,0.045)",
  panelHi: "rgba(255,255,255,0.08)",
  border: "rgba(160,175,255,0.18)",
};

const NAV = ["Home", "Agents", "Warung Watch", "Pricing", "API", "About Us", "Help / FAQ"] as const;
export type NavItem = (typeof NAV)[number];

export const NavIcon: React.FC<{ k: string; size?: number; color?: string }> = ({ k, size = 26, color = "currentColor" }) => {
  const s = { stroke: color, strokeWidth: 2, fill: "none", strokeLinecap: "round" as const, strokeLinejoin: "round" as const };
  const p: Record<string, React.ReactNode> = {
    Home: <path d="M4 11 L12 4 L20 11 V20 H4 Z M10 20 V14 H14 V20" {...s} />,
    Agents: <><rect x="4" y="4" width="7" height="7" rx="2" {...s} /><rect x="13" y="4" width="7" height="7" rx="2" {...s} /><rect x="4" y="13" width="7" height="7" rx="2" {...s} /><rect x="13" y="13" width="7" height="7" rx="2" {...s} /></>,
    "Warung Watch": <path d="M4 10 H20 L18 20 H6 Z M7 10 L9 4 H15 L17 10" {...s} />,
    Pricing: <path d="M4 12 L12 4 H20 V12 L12 20 Z M16 8 h0.01" {...s} />,
    API: <path d="M8 7 L3 12 L8 17 M16 7 L21 12 L16 17 M13.5 5 L10.5 19" {...s} />,
    "About Us": <><circle cx="12" cy="12" r="8" {...s} /><path d="M12 11 V16 M12 8 h0.01" {...s} /></>,
    "Help / FAQ": <><circle cx="12" cy="12" r="8" {...s} /><path d="M9.5 9.5 a2.5 2.5 0 1 1 3.5 2.3 c-0.7 0.3 -1 0.8 -1 1.5 M12 16.5 h0.01" {...s} /></>,
    History: <><circle cx="12" cy="12" r="8" {...s} /><path d="M12 7 V12 L15 14" {...s} /></>,
  };
  return <svg width={size} height={size} viewBox="0 0 24 24">{p[k]}</svg>;
};

/** Sidebar rail + header, with `active` highlighted and optional query-history list. */
export const AppShell: React.FC<{
  active?: NavItem;
  credits?: string;
  lang?: string;
  history?: { today: string[]; earlier?: string[]; highlight?: number };
  children: React.ReactNode;
}> = ({ active = "Home", credits = "3 credits", lang = "EN", history, children }) => {
  const t = useW();
  return (
    <div style={{ position: "absolute", inset: 0, borderRadius: 34, overflow: "hidden", background: "linear-gradient(160deg, #0E1438 0%, #080C26 100%)", border: `1.5px solid ${G.border}`, boxShadow: "0 60px 160px rgba(0,0,0,0.6), 0 0 140px rgba(59,91,255,0.18)", fontFamily: display, color: C.white }}>
      {/* sidebar */}
      <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: SIDEBAR_W, background: "rgba(5,8,28,0.6)", borderRight: `1px solid ${G.border}`, padding: "30px 22px", display: "flex", flexDirection: "column", gap: 8 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "0 10px 26px" }}>
          <div style={{ width: 44, height: 44 }}><Mark frame={200} size={44} bubbleAt={0} bloomAt={0} id="shell" /></div>
          <span style={{ fontSize: 30, fontWeight: 800, letterSpacing: "-0.03em" }}>naktahu<span style={{ color: C.blue }}>.my</span></span>
        </div>
        {NAV.map((n) => {
          const on = n === active;
          return (
            <div key={n} style={{ display: "flex", alignItems: "center", gap: 16, height: 54, padding: "0 16px", borderRadius: 14, background: on ? "rgba(59,91,255,0.2)" : "transparent", color: on ? C.white : C.mute, fontSize: 23, fontWeight: on ? 700 : 500, boxShadow: on ? `inset 3px 0 0 ${C.blueHi}` : "none" }}>
              <NavIcon k={n} size={24} />
              {t(n)}
            </div>
          );
        })}
        {history && (
          <div style={{ marginTop: 22, paddingTop: 20, borderTop: `1px solid ${G.border}`, display: "flex", flexDirection: "column", gap: 6 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, fontFamily: mono, fontSize: 16, letterSpacing: "0.14em", color: C.mute, padding: "0 16px 8px" }}>
              <NavIcon k="History" size={18} /> {t("QUERY HISTORY")}
            </div>
            <div style={{ fontSize: 16, color: C.mute, padding: "4px 16px", fontWeight: 600 }}>{t("Today")}</div>
            {history.today.map((q, i) => (
              <div key={q} style={{ fontSize: 19, padding: "10px 16px", borderRadius: 12, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", background: history.highlight === i ? "rgba(59,91,255,0.2)" : "transparent", color: history.highlight === i ? C.white : "rgba(244,246,255,0.75)" }}>
                {t(q)}
              </div>
            ))}
            {history.earlier && (
              <>
                <div style={{ fontSize: 16, color: C.mute, padding: "10px 16px 4px", fontWeight: 600 }}>{t("Earlier")}</div>
                {history.earlier.map((q) => (
                  <div key={q} style={{ fontSize: 19, padding: "10px 16px", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", color: "rgba(244,246,255,0.55)" }}>{t(q)}</div>
                ))}
              </>
            )}
          </div>
        )}
      </div>
      {/* header */}
      <div style={{ position: "absolute", left: SIDEBAR_W, right: 0, top: 0, height: HEADER_H, borderBottom: `1px solid ${G.border}`, display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0 48px" }}>
        <div style={{ fontSize: 22, color: C.mute, fontWeight: 600 }}>{t("Ask about government")}</div>
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <div style={{ padding: "10px 18px", borderRadius: 999, background: G.panel, border: `1px solid ${G.border}`, fontFamily: mono, fontSize: 19, color: C.white }}>{lang}</div>
          <div style={{ padding: "10px 20px", borderRadius: 999, background: G.amberSoft, border: "1px solid rgba(255,178,56,0.45)", fontSize: 19, fontWeight: 700, color: C.amber }}>{t(credits)}</div>
          <div style={{ width: 46, height: 46, borderRadius: 23, background: `linear-gradient(135deg, ${C.blueHi}, ${C.blueDeep})`, display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 800, fontSize: 20 }}>A</div>
        </div>
      </div>
      <div style={{ position: "absolute", left: SIDEBAR_W, right: 0, top: HEADER_H, bottom: 0 }}>{children}</div>
    </div>
  );
};

/** Page body, positioned in shell-content coordinates (0,0 = just under the header, right of the sidebar). */
export const Page: React.FC<{ children: React.ReactNode; enter?: number }> = ({ children, enter = 0 }) => {
  const frame = useCurrentFrame();
  const p = prog(frame, enter, 16);
  return <div style={{ position: "absolute", inset: 0, padding: "40px 56px", opacity: p, translate: `0 ${(1 - p) * 24}px` }}>{children}</div>;
};

export const H1: React.FC<{ children: React.ReactNode; sub?: string; eyebrow?: string }> = ({ children, sub, eyebrow }) => (
  <div style={{ display: "flex", flexDirection: "column", gap: 10, marginBottom: 30 }}>
    {eyebrow && <div style={{ fontFamily: mono, fontSize: 18, letterSpacing: "0.2em", color: C.amber }}>{eyebrow}</div>}
    <div style={{ fontSize: 50, fontWeight: 800, letterSpacing: "-0.035em", lineHeight: 1.05 }}>{children}</div>
    {sub && <div style={{ fontSize: 24, color: C.mute, lineHeight: 1.4, maxWidth: 1150 }}>{sub}</div>}
  </div>
);

export const Card: React.FC<{ children: React.ReactNode; style?: React.CSSProperties; glow?: boolean }> = ({ children, style, glow }) => (
  <div style={{ background: G.panel, border: `1.5px solid ${glow ? "rgba(123,145,255,0.6)" : G.border}`, borderRadius: 24, padding: 28, boxShadow: glow ? "0 0 60px rgba(59,91,255,0.3)" : "none", ...style }}>{children}</div>
);

/** Translate a child that is a plain string; leave elements alone. */
const useTr = () => {
  const t = useW();
  return (c: React.ReactNode) => (typeof c === "string" ? t(c) : c);
};

export const Label: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const tr = useTr();
  return <div style={{ fontSize: 19, fontWeight: 600, color: C.mute, marginBottom: 10 }}>{tr(children)}</div>;
};

/** Text input that shows a placeholder until `value` has content, with a focus ring while `focus`. */
export const Field: React.FC<{ value: string; placeholder?: string; focus?: boolean; w?: number | string; h?: number; size?: number; caret?: boolean; multiline?: boolean }> = ({
  value,
  placeholder,
  focus,
  w = "100%",
  h = 64,
  size = 23,
  caret,
  multiline,
}) => {
  const frame = useCurrentFrame();
  const t = useW();
  return (
    <div
      style={{
        width: w,
        minHeight: h,
        borderRadius: 16,
        background: "rgba(0,0,0,0.25)",
        border: `1.5px solid ${focus ? C.blueHi : G.border}`,
        boxShadow: focus ? "0 0 0 4px rgba(123,145,255,0.18)" : "none",
        display: "flex",
        alignItems: multiline ? "flex-start" : "center",
        padding: multiline ? "18px 22px" : "0 22px",
        fontSize: size,
        lineHeight: 1.4,
        color: value ? C.white : "rgba(139,147,196,0.75)",
        whiteSpace: multiline ? "normal" : "nowrap",
        overflow: "hidden",
      }}
    >
      <span>
        {value ? t(value) : placeholder && t(placeholder)}
        {focus && caret !== false && <span style={{ display: "inline-block", width: 2.5, height: size * 1.15, marginLeft: 2, background: C.blueHi, verticalAlign: "middle", opacity: Math.floor(frame / 8) % 2 ? 0 : 1 }} />}
      </span>
    </div>
  );
};

export const Chip: React.FC<{ children: React.ReactNode; on?: boolean; size?: number; tone?: "blue" | "green" | "amber" | "red" }> = ({ children, on, size = 20, tone = "blue" }) => {
  const tones = {
    blue: ["rgba(59,91,255,0.28)", C.blueHi],
    green: [G.greenSoft, G.green],
    amber: [G.amberSoft, C.amber],
    red: [G.redSoft, "#FF6B6F"],
  }[tone];
  const tr = useTr();
  return (
    <div style={{ display: "inline-flex", alignItems: "center", gap: 8, padding: `${size * 0.45}px ${size * 0.9}px`, borderRadius: 999, fontSize: size, fontWeight: 600, whiteSpace: "nowrap", background: on ? tones[0] : G.panel, border: `1.5px solid ${on ? tones[1] : G.border}`, color: on ? C.white : "rgba(244,246,255,0.8)" }}>
      {tr(children)}
    </div>
  );
};

/** Primary / secondary button that visibly depresses on `press` and can show a busy spinner. */
export const Button: React.FC<{ children: React.ReactNode; press?: number; kind?: "primary" | "ghost" | "green"; busy?: boolean; size?: number; w?: number | string }> = ({
  children,
  press,
  kind = "primary",
  busy,
  size = 22,
  w,
}) => {
  const frame = useCurrentFrame();
  const tr = useTr();
  const down = press !== undefined && frame >= press - 2 && frame < press + 5;
  const bg = kind === "primary" ? `linear-gradient(135deg, #5872FF, ${C.blueDeep})` : kind === "green" ? "linear-gradient(135deg, #3DDC97, #1FA56C)" : G.panelHi;
  return (
    <div
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        gap: 12,
        width: w,
        padding: `${size * 0.72}px ${size * 1.3}px`,
        borderRadius: 16,
        background: bg,
        border: kind === "ghost" ? `1.5px solid ${G.border}` : "none",
        boxShadow: kind === "ghost" ? "none" : "0 12px 30px rgba(59,91,255,0.35), inset 0 1px 0 rgba(255,255,255,0.25)",
        fontSize: size,
        fontWeight: 700,
        color: kind === "green" ? "#04210F" : "white",
        scale: down ? "0.95" : "1",
        filter: down ? "brightness(1.2)" : "none",
        whiteSpace: "nowrap",
      }}
    >
      {busy && <Spinner size={size} />}
      {tr(children)}
    </div>
  );
};

export const Spinner: React.FC<{ size?: number; color?: string }> = ({ size = 22, color = "white" }) => {
  const frame = useCurrentFrame();
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" style={{ rotate: `${frame * 14}deg` }}>
      <circle cx="12" cy="12" r="9" stroke={color} strokeOpacity="0.25" strokeWidth="3" fill="none" />
      <path d="M12 3 a9 9 0 0 1 9 9" stroke={color} strokeWidth="3" fill="none" strokeLinecap="round" />
    </svg>
  );
};

export const Check: React.FC<{ size?: number; color?: string }> = ({ size = 18, color = G.green }) => (
  <svg width={size} height={size} viewBox="0 0 18 18"><path d="M3 9.5 L7.5 13.5 L15 5" stroke={color} strokeWidth="2.8" fill="none" strokeLinecap="round" strokeLinejoin="round" /></svg>
);

/** Appear with a small rise + fade at `at`; `step` staggers children lists. */
export const Rise: React.FC<{ at: number; children: React.ReactNode; y?: number; style?: React.CSSProperties }> = ({ at, children, y = 22, style }) => {
  const frame = useCurrentFrame();
  const p = prog(frame, at, 14, EXPO_OUT);
  return <div style={{ opacity: p, translate: `0 ${(1 - p) * y}px`, ...style }}>{children}</div>;
};

/** A small "illustrative data" flag, so demo numbers are never mistaken for real figures. */
export const DemoFlag: React.FC = () => {
  const t = useW();
  return <div style={{ position: "absolute", right: 28, bottom: 22, fontFamily: mono, fontSize: 15, letterSpacing: "0.12em", color: "rgba(139,147,196,0.7)" }}>{t("ILLUSTRATIVE DEMO DATA")}</div>;
};

/** Absolutely position a child in APP coordinates, from inside the shell's content area. */
export const Abs: React.FC<{ x: number; y: number; w?: number; h?: number; children: React.ReactNode; style?: React.CSSProperties }> = ({ x, y, w, h, children, style }) => (
  <div style={{ position: "absolute", left: x - SIDEBAR_W, top: y - HEADER_H, width: w, height: h, ...style }}>{children}</div>
);

/** Agent page heading: title, optional plan/credit badge, and the page's real subheading. */
export const Heading: React.FC<{ title: string; sub: string; badge?: string; tone?: "green" | "amber" | "blue" }> = ({ title, sub, badge, tone = "amber" }) => {
  const t = useW();
  return (
    <Abs x={356} y={140} w={1500}>
      <Rise at={0}>
        <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
          <div style={{ fontSize: 50, fontWeight: 800, letterSpacing: "-0.035em" }}>{t(title)}</div>
          {badge && <Chip on tone={tone} size={18}>{badge}</Chip>}
        </div>
        <div style={{ fontSize: 23, color: C.mute, marginTop: 10, maxWidth: 1400, lineHeight: 1.4 }}>{t(sub)}</div>
      </Rise>
    </Abs>
  );
};
