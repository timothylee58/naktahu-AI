import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { BEAT, C, EXPO_OUT, Pill, STEP, Window, clamp, display, mono, pop, prog } from "./core";
import { Mark } from "../Promo/Mark";
import type { CopyKey } from "./copy.bm";
import { useT } from "./i18n";

const S = { stroke: "white", strokeWidth: 1.9, fill: "none", strokeLinecap: "round" as const, strokeLinejoin: "round" as const };
const GLYPH: Record<string, React.ReactNode> = {
  target: (<g {...S}><circle cx="12" cy="12" r="8.5" /><circle cx="12" cy="12" r="4.5" /><circle cx="12" cy="12" r="0.8" fill="white" /></g>),
  docPen: (<g {...S}><path d="M6 3 H14 L18 7 V21 H6 Z" /><path d="M9 11 H15 M9 15 H13" /><path d="M14 3 V7 H18" /></g>),
  heart: (<g {...S}><path d="M12 20 C4 14.5 3 10 5 7 C7 4.5 10.5 5 12 8 C13.5 5 17 4.5 19 7 C21 10 20 14.5 12 20 Z" /><path d="M6 12 H9 L10.5 9.5 L13 14.5 L14.5 12 H18" /></g>),
  globe: (<g {...S}><circle cx="12" cy="12" r="8.5" /><path d="M3.5 12 H20.5 M12 3.5 C8.5 7.5 8.5 16.5 12 20.5 M12 3.5 C15.5 7.5 15.5 16.5 12 20.5" /></g>),
  book: (<g {...S}><path d="M3 6 C6 4.5 9 4.5 12 6.5 C15 4.5 18 4.5 21 6 V19 C18 17.5 15 17.5 12 19.5 C9 17.5 6 17.5 3 19 Z" /><path d="M12 6.5 V19.5" /></g>),
  check: (<g {...S}><rect x="4" y="3.5" width="16" height="17" rx="2.5" /><path d="M8 9 L9.5 10.5 L12 8 M8 15 L9.5 16.5 L12 14 M14 9.5 H17 M14 15.5 H17" /></g>),
  doc: (<g {...S}><path d="M6 3 H14 L18 7 V21 H6 Z" /><path d="M14 3 V7 H18 M9 12 H15 M9 16 H15" /></g>),
  brief: (<g {...S}><rect x="3.5" y="7" width="17" height="12" rx="2.5" /><path d="M9 7 V5 H15 V7 M3.5 12.5 H20.5" /></g>),
  house: (<g {...S}><path d="M4 11 L12 4 L20 11 V20 H4 Z" /><path d="M10 20 V14.5 H14 V20" /></g>),
  gift: (<g {...S}><rect x="4" y="9" width="16" height="11" rx="2" /><path d="M12 9 V20 M4 13 H20 M12 9 C10 5 6.5 6 8 8.5 C9 9 12 9 12 9 C12 9 15 9 16 8.5 C17.5 6 14 5 12 9" /></g>),
  search: (<g {...S}><circle cx="10.5" cy="10.5" r="6.5" /><path d="M15.5 15.5 L20.5 20.5" /></g>),
  cal: (<g {...S}><rect x="3.5" y="5" width="17" height="15.5" rx="2.5" /><path d="M3.5 10 H20.5 M8 3 V7 M16 3 V7" /></g>),
};
const Glyph: React.FC<{ k: string; size: number }> = ({ k, size }) => (
  <svg width={size} height={size} viewBox="0 0 24 24">{GLYPH[k]}</svg>
);

const AGENTS: { id: string; name: CopyKey; badge: CopyKey; icon: string; from: string; to: string }[] = [
  { id: "grant-finder", name: "agent.grant-finder", badge: "badge.free", icon: "target", from: "#FFC25C", to: "#E08A00" },
  { id: "grant-draft-generator", name: "agent.grant-draft-generator", badge: "badge.credit3", icon: "docPen", from: "#FFB238", to: "#D9731A" },
  { id: "health-triage", name: "agent.health-triage", badge: "badge.free", icon: "heart", from: "#FF6B7A", to: "#D12A45" },
  { id: "immigration-navigator", name: "agent.immigration-navigator", badge: "badge.credit1", icon: "globe", from: "#2FD3B5", to: "#119C84" },
  { id: "study-agent", name: "agent.study-agent", badge: "badge.student", icon: "book", from: "#9B7BFF", to: "#5B3BDB" },
  { id: "sme-compliance-navigator", name: "agent.sme-compliance-navigator", badge: "badge.credit1", icon: "check", from: "#5872FF", to: "#2540C9" },
  { id: "compliance-drafter", name: "agent.compliance-drafter", badge: "badge.credit1", icon: "doc", from: "#6F87FF", to: "#3350F0" },
  { id: "retrenchment-navigator", name: "agent.retrenchment-navigator", badge: "badge.free", icon: "brief", from: "#FF8A5B", to: "#D9502A" },
  { id: "property-concierge", name: "agent.property-concierge", badge: "badge.free", icon: "house", from: "#41C7FF", to: "#1682C9" },
  { id: "welfare-eligibility", name: "agent.welfare-eligibility", badge: "badge.free", icon: "gift", from: "#52D98A", to: "#1E9E5A" },
  { id: "research-synthesiser", name: "agent.research-synthesiser", badge: "badge.business", icon: "search", from: "#B98CFF", to: "#7A45E0" },
  { id: "deadline-monitor", name: "agent.deadline-monitor", badge: "badge.pro", icon: "cal", from: "#FF7BC5", to: "#C93A8C" },
];

const Tile: React.FC<{ a: (typeof AGENTS)[number]; iconSize?: number }> = ({ a, iconSize = 44 }) => (
  <div style={{ width: iconSize * 1.45, height: iconSize * 1.45, borderRadius: iconSize * 0.4, background: `linear-gradient(145deg, ${a.from}, ${a.to})`, display: "flex", alignItems: "center", justifyContent: "center", boxShadow: `0 10px 26px ${a.to}66`, flexShrink: 0 }}>
    <Glyph k={a.icon} size={iconSize} />
  </div>
);

const Badge: React.FC<{ k: CopyKey }> = ({ k }) => {
  const t = useT();
  const free = k === "badge.free";
  return (
    <div style={{ fontFamily: mono, fontSize: 18, fontWeight: 500, padding: "5px 11px", borderRadius: 8, background: free ? "rgba(61,220,151,0.14)" : "rgba(255,178,56,0.14)", color: free ? "#8FF0C4" : "#FFD08A", border: `1px solid ${free ? "rgba(61,220,151,0.4)" : "rgba(255,178,56,0.4)"}`, whiteSpace: "nowrap" }}>
      {t(k)}
    </div>
  );
};

/** Bar 9 (breakdown) — the routing hint, then all 12 agents cascading on 16ths. */
export const HubMock: React.FC = () => {
  const frame = useCurrentFrame();
  const t = useT();
  const [pre, post] = t("hub.suggest").split("{agent}");
  return (
    <Window path="/agents">
      <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
        <div style={{ ...pop(frame, 0), alignSelf: "flex-start", display: "flex", alignItems: "center", gap: 14, padding: "14px 22px", borderRadius: 18, background: "rgba(255,178,56,0.12)", border: "1.5px solid rgba(255,178,56,0.5)", fontSize: 25, fontWeight: 600, transformOrigin: "0 50%" }}>
          <span>💡</span>
          <span>{pre}<b style={{ color: C.amber }}>{t("agent.grant-finder")}</b>{post}</span>
          <span style={{ marginLeft: 8, padding: "6px 14px", borderRadius: 10, background: C.amber, color: "#1A1204", fontWeight: 800 }}>{t("hub.open")}</span>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 14 }}>
          {AGENTS.map((a, i) => {
            const at = 8 + i * STEP;
            const p = prog(frame, at, 9);
            return (
              <div
                key={a.id}
                style={{
                  height: 128,
                  borderRadius: 20,
                  padding: "14px 16px",
                  background: "rgba(255,255,255,0.045)",
                  border: `1.5px solid ${i === 0 ? "rgba(255,178,56,0.6)" : C.line}`,
                  display: "flex",
                  flexDirection: "column",
                  justifyContent: "space-between",
                  opacity: p,
                  scale: `${0.7 + 0.3 * p}`,
                  translate: `0 ${(1 - p) * 30}px`,
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                  <Tile a={a} iconSize={30} />
                  <Badge k={a.badge} />
                </div>
                <div style={{ fontSize: 22, fontWeight: 800, lineHeight: 1.15, letterSpacing: "-0.01em" }}>{t(a.name)}</div>
              </div>
            );
          })}
        </div>
      </div>
    </Window>
  );
};

const GrantCard: React.FC<{ name: string; agency: string; amount: string; match: number; cta: string; at: number }> = ({ name, agency, amount, match, cta, at }) => {
  const frame = useCurrentFrame();
  const t = useT();
  const m = interpolate(frame, [at, at + 14], [0, match], { ...clamp, easing: EXPO_OUT });
  return (
    <div style={{ ...pop(frame, at), borderRadius: 26, padding: "24px 28px", background: "rgba(255,255,255,0.05)", border: "1.5px solid rgba(255,178,56,0.45)", display: "flex", justifyContent: "space-between", alignItems: "center", gap: 20 }}>
      <div style={{ display: "flex", flexDirection: "column", gap: 8, minWidth: 0 }}>
        <div style={{ fontSize: 30, fontWeight: 800, letterSpacing: "-0.01em" }}>{name}</div>
        <div style={{ fontSize: 24, color: C.mute }}>{agency}</div>
        <div style={{ display: "flex", alignItems: "center", gap: 18, marginTop: 6 }}>
          <span style={{ fontFamily: mono, fontSize: 30, fontWeight: 500, color: C.amber }}>{amount}</span>
          <span style={{ fontSize: 24, fontWeight: 700, color: C.blueHi }}>{cta}</span>
        </div>
      </div>
      <div style={{ textAlign: "right", flexShrink: 0 }}>
        <div style={{ fontFamily: mono, fontSize: 56, fontWeight: 500, color: "#3DDC97", lineHeight: 1 }}>{Math.round(m)}%</div>
        <div style={{ fontSize: 22, color: "#8FF0C4", marginTop: 6 }}>{t("grant.matchLabel")}</div>
      </div>
    </div>
  );
};

/** Bar 10 — Grant Finder with real programmes from the grant database seed. */
export const GrantMock: React.FC = () => {
  const frame = useCurrentFrame();
  const t = useT();
  const matching = frame >= 6 && frame < BEAT;
  return (
    <Window path="/agents/grant-finder">
      <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
          <Pill size={26} bg="rgba(255,178,56,0.2)" border={C.amber}>{t("grant.chipAI")}</Pill>
          <Pill size={26} bg="rgba(255,255,255,0.05)" border={C.line} color={C.mute}>{t("grant.chipFintech")}</Pill>
          <Pill size={26} bg="rgba(255,255,255,0.05)" border={C.line} color={C.mute}>{t("grant.chipAgri")}</Pill>
          <Pill size={26} bg="rgba(255,255,255,0.05)" border={C.line} color={C.mute}>{t("grant.chipMonths")}</Pill>
        </div>
        <div style={{ fontFamily: mono, fontSize: 26, color: matching ? C.amber : "#8FF0C4", height: 34 }}>
          {frame < 6 ? "" : matching ? t("grant.matching") : t("grant.count")}
        </div>
        <GrantCard name="Malaysia Digital Acceleration Grant (MDAG)" agency="MDEC" amount="RM100k–500k" match={92} cta={t("grant.apply")} at={BEAT} />
        <GrantCard name="CIP Spark" agency="Cradle Fund" amount="RM50k–150k" match={88} cta={t("grant.draft")} at={BEAT * 2 - 2} />
        <div style={{ opacity: prog(frame, BEAT * 3 - 2, 8) * 0.6, borderRadius: 22, padding: "18px 26px", border: `1.5px dashed ${C.line}`, display: "flex", flexDirection: "column", gap: 6 }}>
          <div style={{ fontSize: 22, color: C.mute }}>{t("grant.nearMiss")}</div>
          <div style={{ fontSize: 28, fontWeight: 700 }}>CIP Sprint · Cradle Fund</div>
        </div>
      </div>
    </Window>
  );
};

/** Bar 11 — Grant Draft Generator assembling the application. */
export const DraftMock: React.FC = () => {
  const frame = useCurrentFrame();
  const t = useT();
  const Line: React.FC<{ w: number; at: number }> = ({ w, at }) => (
    <div style={{ height: 14, borderRadius: 7, background: "#DDE2F5", width: `${w * prog(frame, at, 10)}%` }} />
  );
  const sec = (k: CopyKey, at: number) => (
    <div style={{ fontSize: 30, fontWeight: 800, color: "#141A3A", opacity: prog(frame, at, 6) }}>{t(k)}</div>
  );
  return (
    <Window path="/agents/grant-draft-generator">
      <div style={{ display: "flex", flexDirection: "column", gap: 20, height: "100%" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <Pill size={26} bg="rgba(255,178,56,0.2)" border={C.amber}>CIP Spark</Pill>
          <div style={{ display: "flex", borderRadius: 14, overflow: "hidden", border: `1.5px solid ${C.line}` }}>
            <div style={{ padding: "10px 22px", fontSize: 24, fontWeight: 800, background: C.blue }}>PDF</div>
            <div style={{ padding: "10px 22px", fontSize: 24, fontWeight: 700, color: C.mute }}>DOCX</div>
          </div>
          <div style={{ marginLeft: "auto" }}>
            <Pill size={22} bg="rgba(255,178,56,0.14)" border="rgba(255,178,56,0.5)" color="#FFD08A">{t("badge.credit3")}</Pill>
          </div>
        </div>
        <div style={{ flex: 1, borderRadius: 18, background: "#F7F8FD", padding: "30px 36px", display: "flex", flexDirection: "column", gap: 14, boxShadow: "0 20px 50px rgba(0,0,0,0.35)" }}>
          {sec("draft.exec", 0)}
          <Line w={96} at={3} />
          <Line w={88} at={6} />
          <Line w={62} at={9} />
          <div style={{ height: 8 }} />
          {sec("draft.funds", BEAT)}
          {[
            [70, C.blue],
            [45, C.amber],
            [28, "#3DDC97"],
          ].map(([w, c], i) => (
            <div key={i} style={{ display: "flex", alignItems: "center", gap: 14 }}>
              <div style={{ width: 120, height: 12, borderRadius: 6, background: "#DDE2F5" }} />
              <div style={{ height: 22, borderRadius: 6, background: String(c), width: `${Number(w) * prog(frame, BEAT + 3 + i * 3, 10) * 0.7}%` }} />
            </div>
          ))}
          <div style={{ height: 8 }} />
          {sec("draft.checklist", BEAT * 2)}
          {[t("draft.item1"), t("draft.item2"), t("draft.item3")].map((label, i) => {
            const on = frame >= BEAT * 2 + 4 + i * 3;
            return (
              <div key={label} style={{ display: "flex", alignItems: "center", gap: 14, fontSize: 26, color: "#2A3160", opacity: prog(frame, BEAT * 2 + 2 + i * 3, 6) }}>
                <div style={{ width: 28, height: 28, borderRadius: 8, border: "2.5px solid #3B5BFF", background: on ? C.blue : "transparent", display: "flex", alignItems: "center", justifyContent: "center" }}>
                  {on && <svg width="16" height="16" viewBox="0 0 16 16"><path d="M3 8.5 L6.5 12 L13 4.5" stroke="white" strokeWidth="2.6" fill="none" strokeLinecap="round" /></svg>}
                </div>
                {label}
              </div>
            );
          })}
        </div>
      </div>
    </Window>
  );
};

/** Bar 12 — Health Triage, free. */
export const TriageMock: React.FC = () => {
  const frame = useCurrentFrame();
  const t = useT();
  const sev = frame >= BEAT ? 1 : -1;
  const pulse = Math.exp(-(frame % BEAT) / 3.2);
  return (
    <Window path="/agents/health-triage">
      <div style={{ display: "flex", flexDirection: "column", gap: 22 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 16, padding: "18px 24px", borderRadius: 18, background: `rgba(224,40,58,${0.8 + pulse * 0.2})`, fontSize: 30, fontWeight: 800 }}>
          <svg width="30" height="30" viewBox="0 0 24 24"><path d="M5 4 H9 L11 9 L8.5 10.5 C9.5 12.8 11.2 14.5 13.5 15.5 L15 13 L20 15 V19 C20 20 19 21 18 21 C10 20.5 3.5 14 3 6 C3 5 4 4 5 4 Z" fill="white" /></svg>
          {t("triage.emergency")}
        </div>
        <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
          <span style={{ fontFamily: mono, fontSize: 22, color: C.mute, letterSpacing: "0.12em" }}>{t("triage.symptomLabel")}</span>
          {[t("triage.s1"), t("triage.s2"), t("triage.s3")].map((label, i) => (
            <div key={label} style={{ ...pop(frame, 2 + i * 3) }}>
              <Pill size={26}>{label}</Pill>
            </div>
          ))}
        </div>
        <div style={{ display: "flex", borderRadius: 18, overflow: "hidden", border: `1.5px solid ${C.line}` }}>
          {[t("triage.mild"), t("triage.moderate"), t("triage.severe")].map((label, i) => (
            <div key={label} style={{ flex: 1, textAlign: "center", padding: "16px 0", fontSize: 28, fontWeight: 800, background: i === sev ? C.amber : "transparent", color: i === sev ? "#1A1204" : C.mute }}>
              {label}
            </div>
          ))}
        </div>
        <div style={{ ...pop(frame, BEAT * 2), transformOrigin: "50% 0", display: "flex", alignItems: "center", gap: 20, padding: "28px 30px", borderRadius: 24, background: "linear-gradient(135deg, rgba(255,178,56,0.28), rgba(255,178,56,0.1))", border: "2px solid rgba(255,178,56,0.7)" }}>
          <div style={{ width: 64, height: 64, borderRadius: 32, background: C.amber, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 38, fontWeight: 800, color: "#1A1204", flexShrink: 0 }}>!</div>
          <div style={{ fontSize: 38, fontWeight: 800, lineHeight: 1.15 }}>{t("triage.result")}</div>
        </div>
        <div style={{ display: "flex", gap: 14, opacity: prog(frame, BEAT * 3, 8) }}>
          <Pill size={26} bg="rgba(255,255,255,0.06)" border={C.line}>{t("triage.nearby")}</Pill>
          <Pill size={26} bg={C.blue} border={C.blue}>{t("triage.pdf")}</Pill>
        </div>
      </div>
    </Window>
  );
};

const INTENTS: [string, CopyKey][] = [
  ["💼", "imm.work"],
  ["🎓", "imm.study"],
  ["✈️", "imm.visit"],
  ["🏢", "imm.business"],
  ["🔄", "imm.extend"],
  ["🛂", "imm.mdac"],
  ["🪪", "imm.eplks"],
  ["💎", "imm.pvip"],
];

/** Bar 13 — Immigration Navigator's eight intents, then the result. */
export const ImmigrationMock: React.FC = () => {
  const frame = useCurrentFrame();
  const t = useT();
  const sel = frame >= BEAT;
  const sheet = prog(frame, BEAT * 2, 10);
  return (
    <Window path="/agents/immigration-navigator">
      <div style={{ position: "relative", height: "100%" }}>
        <div style={{ fontFamily: mono, fontSize: 22, color: C.amber, letterSpacing: "0.14em" }}>{t("imm.step")}</div>
        <div style={{ fontSize: 36, fontWeight: 800, margin: "8px 0 22px" }}>{t("imm.prompt")}</div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 14 }}>
          {INTENTS.map(([e, k], i) => {
            const on = sel && i === 0;
            return (
              <div
                key={k}
                style={{
                  ...pop(frame, i * 1.5),
                  height: 170,
                  borderRadius: 22,
                  padding: 18,
                  background: on ? "rgba(47,211,181,0.18)" : "rgba(255,255,255,0.045)",
                  border: `2px solid ${on ? "#2FD3B5" : C.line}`,
                  boxShadow: on ? "0 0 40px rgba(47,211,181,0.35)" : "none",
                  display: "flex",
                  flexDirection: "column",
                  justifyContent: "space-between",
                }}
              >
                <div style={{ fontSize: 46 }}>{e}</div>
                <div style={{ fontSize: 23, fontWeight: 800, lineHeight: 1.15 }}>{t(k)}</div>
              </div>
            );
          })}
        </div>
        <div
          style={{
            position: "absolute",
            left: -36,
            right: -36,
            bottom: -36,
            height: 380,
            translate: `0 ${(1 - sheet) * 420}px`,
            borderRadius: "30px 30px 0 0",
            background: "linear-gradient(180deg, rgba(20,30,70,0.99), rgba(12,17,46,0.99))",
            borderTop: "2px solid rgba(47,211,181,0.6)",
            padding: "30px 40px",
            display: "flex",
            flexDirection: "column",
            gap: 16,
            boxShadow: "0 -30px 60px rgba(0,0,0,0.5)",
          }}
        >
          <div style={{ fontSize: 30, fontWeight: 700, lineHeight: 1.25 }}>{t("imm.result")}</div>
          {[t("imm.row1"), t("imm.row2"), t("imm.row3")].map((label, i) => (
            <div key={label} style={{ display: "flex", alignItems: "center", gap: 14, fontSize: 28, opacity: prog(frame, BEAT * 2 + 4 + i * 3, 6) }}>
              <div style={{ width: 30, height: 30, borderRadius: 15, background: "#2FD3B5", display: "flex", alignItems: "center", justifyContent: "center" }}>
                <svg width="16" height="16" viewBox="0 0 16 16"><path d="M3 8.5 L6.5 12 L13 4.5" stroke="#06231D" strokeWidth="2.8" fill="none" strokeLinecap="round" /></svg>
              </div>
              {label}
            </div>
          ))}
          <div style={{ ...pop(frame, BEAT * 3), transformOrigin: "0 50%", marginTop: 4 }}>
            <Pill size={28} bg="#2FD3B5" border="#2FD3B5" color="#06231D">{t("imm.portal")}</Pill>
          </div>
        </div>
      </div>
    </Window>
  );
};

/** Bar 14 — Study Agent: scan a question, get quizzed. */
export const StudyMock: React.FC = () => {
  const frame = useCurrentFrame();
  const t = useT();
  const scanY = interpolate(frame, [4, 26], [0, 1], clamp);
  const quiz = frame >= BEAT * 2 - 2;
  return (
    <Window path="/agents/study-agent">
      <div style={{ display: "flex", flexDirection: "column", gap: 20, height: "100%" }}>
        <div style={{ display: "flex", gap: 10 }}>
          {[t("study.paste"), t("study.pdf"), t("study.scan")].map((label, i) => (
            <Pill key={label} size={24} bg={i === 2 ? C.blue : "rgba(255,255,255,0.05)"} border={i === 2 ? C.blue : C.line} color={i === 2 ? "white" : C.mute}>
              {label}
            </Pill>
          ))}
          <div style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
            {["SPM", "STPM"].map((label, i) => (
              <Pill key={label} size={24} bg={i === 0 ? "rgba(155,123,255,0.25)" : "transparent"} border={i === 0 ? "#9B7BFF" : C.line} color={i === 0 ? "white" : C.mute}>
                {label}
              </Pill>
            ))}
          </div>
        </div>
        {!quiz ? (
          <div style={{ position: "relative", flex: 1, borderRadius: 20, background: "#EEF0F8", padding: 36, overflow: "hidden", rotate: "-1.5deg" }}>
            <div style={{ fontSize: 24, fontFamily: mono, color: "#6A7196" }}>{t("study.paperHeader")}</div>
            <div style={{ fontSize: 40, fontWeight: 800, color: "#141A3A", marginTop: 14 }}>1. {t("study.question")}</div>
            {[92, 80, 86, 60].map((w, i) => (
              <div key={i} style={{ height: 14, borderRadius: 7, background: "#D3D8EA", width: `${w}%`, marginTop: 22 }} />
            ))}
            <div style={{ position: "absolute", left: 0, right: 0, top: `${scanY * 100}%`, height: 6, background: C.blueHi, boxShadow: `0 0 30px 10px rgba(123,145,255,0.55)` }} />
            <div style={{ position: "absolute", right: 24, bottom: 20, fontFamily: mono, fontSize: 24, color: C.blue }}>{t("study.scanning")}</div>
          </div>
        ) : (
          <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 20 }}>
            <div style={{ fontFamily: mono, fontSize: 24, letterSpacing: "0.14em", color: "#C7B6FF" }}>{t("study.quiz")}</div>
            <div style={{ fontSize: 38, fontWeight: 800 }}>{t("study.question")}</div>
            <div style={{ ...pop(frame, BEAT * 2), transformOrigin: "0 50%", alignSelf: "flex-start", fontSize: 32, padding: "18px 26px", borderRadius: 20, background: "rgba(255,255,255,0.06)", border: `1.5px solid ${C.line}` }}>
              {t("study.answer")}
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 24 }}>
              <div style={{ ...pop(frame, BEAT * 2 + 6) }}>
                <Pill size={30} bg="rgba(61,220,151,0.2)" border="#3DDC97" color="#8FF0C4">✓ {t("study.correct")}</Pill>
              </div>
              <div style={{ ...pop(frame, BEAT * 3), fontFamily: mono, fontSize: 64, fontWeight: 500, color: "white", marginLeft: "auto" }}>{t("study.score")}</div>
            </div>
          </div>
        )}
      </div>
    </Window>
  );
};

/** Bar 15 — Warung Watch: crowd-reported busyness and a price trend. */
export const WarungMock: React.FC = () => {
  const frame = useCurrentFrame();
  const t = useT();
  const name = t("warung.name");
  const typed = Math.floor(interpolate(frame, [0, 10], [0, name.length], clamp));
  const draw = interpolate(frame, [BEAT * 2, BEAT * 3 + 4], [0, 1], { ...clamp, easing: EXPO_OUT });
  const pts = [0.62, 0.58, 0.6, 0.5, 0.46, 0.4, 0.3];
  const W = 820;
  const Hh = 170;
  const path = pts.map((y, i) => `${i === 0 ? "M" : "L"} ${(i / (pts.length - 1)) * W} ${y * Hh}`).join(" ");
  return (
    <Window path="/warung-watch">
      <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
        <div style={{ display: "flex", gap: 14 }}>
          <div style={{ flex: 1, height: 80, borderRadius: 20, border: "1.5px solid rgba(123,145,255,0.5)", background: "rgba(255,255,255,0.05)", display: "flex", alignItems: "center", padding: "0 26px", fontSize: 32 }}>
            {name.slice(0, typed)}
            <span style={{ width: 3, height: 34, marginLeft: 3, background: C.blueHi, opacity: frame < 12 ? 1 : 0 }} />
          </div>
          <Pill size={28} bg={C.blue} border={C.blue}>{t("warung.check")}</Pill>
        </div>
        <div style={{ ...pop(frame, BEAT), transformOrigin: "0 50%", display: "flex", alignItems: "center", gap: 22, padding: "24px 30px", borderRadius: 24, background: "rgba(255,178,56,0.14)", border: "2px solid rgba(255,178,56,0.6)" }}>
          <div style={{ width: 34, height: 34, borderRadius: 17, background: "#FFC23D", boxShadow: "0 0 24px #FFC23D" }} />
          <div>
            <div style={{ fontSize: 46, fontWeight: 800 }}>{t("warung.status")}</div>
            <div style={{ fontSize: 24, color: C.mute }}>{t("warung.reports")}</div>
          </div>
        </div>
        <div style={{ opacity: prog(frame, BEAT * 2 - 3, 6), borderRadius: 24, padding: "22px 30px", background: "rgba(255,255,255,0.04)", border: `1.5px solid ${C.line}` }}>
          <div style={{ fontSize: 28, fontWeight: 800, marginBottom: 14 }}>{t("warung.chart")}</div>
          <svg width={W} height={Hh + 20} style={{ overflow: "visible" }}>
            <path d={path} fill="none" stroke={C.amber} strokeWidth={5} strokeLinecap="round" strokeLinejoin="round" pathLength={1} strokeDasharray={1} strokeDashoffset={1 - draw} />
            {pts.map((y, i) => (
              <circle key={i} cx={(i / (pts.length - 1)) * W} cy={y * Hh} r={8} fill={C.amber} opacity={draw >= i / (pts.length - 1) ? 1 : 0} />
            ))}
          </svg>
        </div>
        <div style={{ ...pop(frame, BEAT * 3 + 2), transformOrigin: "0 50%" }}>
          <Pill size={26} bg="rgba(255,255,255,0.06)" border={C.line}>{t("warung.nearby")}</Pill>
        </div>
      </div>
    </Window>
  );
};

const MiniCard: React.FC<{ a: (typeof AGENTS)[number]; at: number; children: React.ReactNode }> = ({ a, at, children }) => {
  const frame = useCurrentFrame();
  const t = useT();
  const p = prog(frame, at, 8);
  return (
    <div
      style={{
        width: 470,
        height: 390,
        borderRadius: 30,
        padding: 28,
        background: "linear-gradient(165deg, rgba(24,31,78,0.97), rgba(10,14,40,0.98))",
        border: `1.5px solid ${a.from}88`,
        boxShadow: `0 30px 70px rgba(0,0,0,0.5), 0 0 60px ${a.to}33`,
        display: "flex",
        flexDirection: "column",
        gap: 18,
        opacity: p,
        scale: `${1.25 - 0.25 * p}`,
        filter: `blur(${(1 - p) * 8}px)`,
        fontFamily: display,
        color: C.white,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
        <Tile a={a} iconSize={32} />
        <div>
          <div style={{ fontSize: 28, fontWeight: 800, lineHeight: 1.1 }}>{t(a.name)}</div>
          <div style={{ fontFamily: mono, fontSize: 18, color: C.mute }}>/agents/{a.id}</div>
        </div>
      </div>
      {children}
    </div>
  );
};

/** Bar 16 — four more agents, one per beat. */
export const MoreMock: React.FC = () => {
  const frame = useCurrentFrame();
  const t = useT();
  const byId = (id: string) => AGENTS.find((a) => a.id === id)!;
  const ring = prog(frame, 4, 14);
  return (
    <div style={{ width: 960, height: 800, display: "grid", gridTemplateColumns: "470px 470px", gap: 20 }}>
      <MiniCard a={byId("sme-compliance-navigator")} at={0}>
        <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
          <svg width="84" height="84" viewBox="0 0 84 84">
            <circle cx="42" cy="42" r="34" stroke="rgba(255,255,255,0.12)" strokeWidth="9" fill="none" />
            <circle cx="42" cy="42" r="34" stroke={C.blueHi} strokeWidth="9" fill="none" strokeLinecap="round" pathLength={1} strokeDasharray={1} strokeDashoffset={1 - (5 / 8) * ring} transform="rotate(-90 42 42)" />
          </svg>
          <div style={{ fontSize: 30, fontWeight: 800 }}>{t("more.patuhiProgress")}</div>
        </div>
        {[t("more.patuhi1"), t("more.patuhi2"), t("more.patuhi3")].map((label, i) => (
          <div key={label} style={{ display: "flex", alignItems: "center", gap: 12, fontSize: 24, color: i < 2 ? C.white : C.mute }}>
            <span style={{ color: i < 2 ? "#3DDC97" : C.mute, fontWeight: 800 }}>{i < 2 ? "✓" : "○"}</span>
            {label}
          </div>
        ))}
      </MiniCard>
      <MiniCard a={byId("deadline-monitor")} at={BEAT}>
        <div style={{ fontSize: 26, color: C.mute }}>{t("more.deadlineDoc")}</div>
        <div style={{ display: "flex", alignItems: "baseline", gap: 14 }}>
          <span style={{ fontFamily: mono, fontSize: 120, fontWeight: 500, lineHeight: 1, color: "#FF9BD2" }}>14</span>
          <span style={{ fontSize: 36, fontWeight: 800 }}>{t("more.daysLeft")}</span>
        </div>
      </MiniCard>
      <MiniCard a={byId("retrenchment-navigator")} at={BEAT * 2}>
        <div style={{ fontSize: 26, color: C.mute }}>{t("more.retrenchSub")}</div>
        <Pill size={28} bg="rgba(61,220,151,0.16)" border="#3DDC97" color="#8FF0C4">{t("more.retrenchEis")}</Pill>
        <Pill size={26} bg="rgba(255,255,255,0.05)" border={C.line}>{t("more.checklist")}</Pill>
      </MiniCard>
      <MiniCard a={byId("property-concierge")} at={BEAT * 3}>
        <div style={{ fontSize: 30, fontWeight: 800, lineHeight: 1.25, color: "#8FE3FF" }}>{t("more.propertyTier")}</div>
        <Pill size={26} bg="rgba(37,211,102,0.16)" border="rgba(37,211,102,0.7)">{t("more.propertyShare")}</Pill>
      </MiniCard>
    </div>
  );
};

const CODE = [
  ["curl -X POST $API/api/v1/public/query \\", C.white],
  ['  -H "Content-Type: application/json" \\', "#AFC0FF"],
  ['  -H "X-NakTahu-Key: YOUR_API_KEY" \\', "#AFC0FF"],
  [`  -d '{"query": "Cukai pendapatan 2025?", "language": "bm"}'`, "#FFD08A"],
] as const;

/** Bar 17 — Developer API and the embeddable widget. */
export const ApiMock: React.FC = () => {
  const frame = useCurrentFrame();
  const t = useT();
  const total = CODE.reduce((n, [l]) => n + l.length, 0);
  const typed = interpolate(frame, [0, 26], [0, total], clamp);
  let used = 0;
  return (
    <Window path="/developer">
      <div style={{ display: "flex", flexDirection: "column", gap: 18, height: "100%", position: "relative" }}>
        <div style={{ display: "flex", gap: 10 }}>
          {["curl", "Python", "TypeScript"].map((label, i) => (
            <Pill key={label} size={24} bg={i === 0 ? C.blue : "rgba(255,255,255,0.05)"} border={i === 0 ? C.blue : C.line} color={i === 0 ? "white" : C.mute}>
              {label}
            </Pill>
          ))}
        </div>
        <div style={{ borderRadius: 20, background: "#070A1C", border: `1.5px solid ${C.line}`, padding: "24px 26px", fontFamily: mono, fontSize: 23, lineHeight: 1.6 }}>
          {CODE.map(([l, col], i) => {
            const vis = Math.max(0, Math.min(l.length, Math.floor(typed - used)));
            used += l.length;
            return (
              <div key={i} style={{ color: col, whiteSpace: "pre", minHeight: 37 }}>
                {l.slice(0, vis)}
              </div>
            );
          })}
        </div>
        <div style={{ display: "flex", gap: 18, opacity: prog(frame, BEAT * 2, 8) }}>
          <div style={{ flex: 1, borderRadius: 20, background: "#070A1C", border: "1.5px solid rgba(61,220,151,0.4)", padding: "18px 24px", fontFamily: mono, fontSize: 22, lineHeight: 1.6 }}>
            <div style={{ color: "#3DDC97" }}>200 OK</div>
            <div style={{ color: "#C9D0FF" }}>{'{ "answer": "…",'}</div>
            <div style={{ color: "#C9D0FF" }}>{'  "citations": [ … ] }'}</div>
          </div>
          <div style={{ width: 300, borderRadius: 20, background: "rgba(255,255,255,0.04)", border: `1.5px solid ${C.line}`, padding: "16px 18px", display: "flex", flexDirection: "column", gap: 10 }}>
            <div style={{ fontFamily: mono, fontSize: 18, color: C.mute }}>{t("api.usage")}</div>
            <div style={{ display: "flex", alignItems: "flex-end", gap: 5, height: 90 }}>
              {Array.from({ length: 14 }).map((_, i) => (
                <div key={i} style={{ flex: 1, borderRadius: 3, background: C.blueHi, height: `${(20 + ((i * 37) % 60) + i * 2) * prog(frame, BEAT * 2 + i, 8)}%` }} />
              ))}
            </div>
          </div>
        </div>
        <div style={{ ...pop(frame, BEAT * 3), position: "absolute", right: 0, bottom: 0, display: "flex", alignItems: "center", gap: 14, padding: "14px 20px 14px 14px", borderRadius: 999, background: "rgba(59,91,255,0.2)", border: "1.5px solid rgba(123,145,255,0.6)", transformOrigin: "100% 100%" }}>
          <div style={{ width: 56, height: 56 }}>
            <Mark frame={frame} size={56} bubbleAt={BEAT * 3 - 30} bloomAt={BEAT * 3 - 26} id="api" />
          </div>
          <span style={{ fontFamily: mono, fontSize: 22 }}>widget.js</span>
        </div>
      </div>
    </Window>
  );
};
