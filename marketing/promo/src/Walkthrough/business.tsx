import React from "react";
import { useCurrentFrame } from "remotion";
import { C, display, mono, prog, streamed, typed } from "./engine";
import { Abs, AppShell, Button, Card, Check, Chip, DemoFlag, Field, G, Heading, Label, Rise } from "./ui";
import { useTx, useW } from "./i18n";
import type { Chapter, Script } from "./Walkthrough";

/**
 * Walkthrough 02 — Run your business. One Sdn Bhd owner through the agents
 * hub, Grant Finder, Grant Draft Generator, PatuhiKu and Deadline Monitor.
 * Agent names, fields, buttons and pricing are the product's real strings;
 * grant/deadline rows are illustrative and flagged on screen as demo data.
 */

// ---------------------------------------------------------------- 1. agents hub
const AGENTS: { name: string; badge: string; tone: "green" | "amber" | "blue"; desc: string; icon: string }[] = [
  { name: "Compliance Drafter", badge: "Free", tone: "green", desc: "A ready-to-use compliance report — review it before you download.", icon: "📄" },
  { name: "Study Agent", badge: "Student", tone: "blue", desc: "Upload your SPM past paper — an explanation for every question.", icon: "🎓" },
  { name: "Immigration Navigator", badge: "Free", tone: "green", desc: "Document checklist, warnings, and official references.", icon: "🛂" },
  { name: "Health Triage", badge: "Free", tone: "green", desc: "Symptom intake → KKM guidance → clinic or hospital.", icon: "🩺" },
  { name: "Grant Finder", badge: "New", tone: "amber", desc: "Match your profile to government grants (MDEC, TEKUN, MARA…).", icon: "🎯" },
  { name: "Research Synthesiser", badge: "Business", tone: "blue", desc: "Fan-out across up to 13 domains, merged into one synthesis.", icon: "🧭" },
  { name: "Retrenchment Navigator", badge: "New", tone: "amber", desc: "EIS claim eligibility, termination benefits, next steps.", icon: "🧾" },
  { name: "Property Concierge", badge: "New", tone: "amber", desc: "Tenancy, strata and land-title answers, plus a shareable brief.", icon: "🏠" },
  { name: "PatuhiKu", badge: "Free", tone: "green", desc: "LHDN, EPF/SOCSO/EIS and SSM obligations for your SME.", icon: "✅" },
  { name: "Grant Draft Generator", badge: "Free", tone: "green", desc: "Executive summary, use of funds, document checklist.", icon: "✍️" },
  { name: "Deadline Monitor", badge: "Pro", tone: "blue", desc: "Regulatory deadline calendar with proactive alerts.", icon: "⏰" },
  { name: "Check Assistance", badge: "New", tone: "amber", desc: "Match your household to cost-of-living assistance schemes.", icon: "🤝" },
];
const cardPos = (i: number) => ({ x: 356 + (i % 4) * 382, y: 330 + Math.floor(i / 4) * 222 });
const H1 = { hover: 300, click: 420 };

const Hub: React.FC = () => {
  const t = useW();
  const tx = useTx();
  const frame = useCurrentFrame();
  return (
    <AppShell active="Agents" credits="8 credits">
      <Heading title="NakTahu Agents" sub="Step-by-step helpers for everyday government tasks — answers grounded in official sources, not guesses." />
      {AGENTS.map((a, i) => {
        const { x, y } = cardPos(i);
        const hot = i === 4 && frame >= H1.hover;
        const p = prog(frame, 20 + i * 3, 14);
        return (
          <Abs key={a.name} x={x} y={y} w={360} h={200}>
            <div style={{ height: 200, boxSizing: "border-box", padding: 22, borderRadius: 22, background: hot ? "rgba(59,91,255,0.18)" : G.panel, border: `1.5px solid ${hot ? C.blueHi : G.border}`, boxShadow: hot ? "0 0 60px rgba(59,91,255,0.35)" : "none", opacity: p, translate: `0 ${(1 - p) * 30 - (hot ? 6 : 0)}px`, display: "flex", flexDirection: "column", gap: 10 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div style={{ width: 50, height: 50, borderRadius: 14, background: "rgba(59,91,255,0.2)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 28 }}>{tx(a.icon)}</div>
                <Chip on tone={a.tone} size={15}>{tx(a.badge)}</Chip>
              </div>
              <div style={{ fontSize: 24, fontWeight: 800 }}>{tx(a.name)}</div>
              <div style={{ fontSize: 17, lineHeight: 1.35, color: C.mute }}>{tx(a.desc)}</div>
            </div>
          </Abs>
        );
      })}
      <Abs x={356} y={1010} w={1500}>
        <div style={{ fontSize: 18, color: C.mute, opacity: prog(frame, 60, 12) }}>{t("Some agents use \"credits\" — each credit is RM5 and covers one full use of that agent. Business plans have no limit.")}</div>
      </Abs>
    </AppShell>
  );
};

const ch1: Chapter = {
  name: "Agents",
  title: "Agents",
  line: "Twelve specialists for the paperwork of life.",
  Screen: Hub,
  cam: [
    { f: 0, x: 960, y: 540, z: 1 },
    { f: 110, x: 960, y: 560, z: 1.08 },
    { f: 190, x: 1000, y: 900, z: 1.6 },
    { f: 270, x: 1000, y: 900, z: 1.6 },
    { f: 310, x: 700, y: 640, z: 1.55 },
    { f: 470, x: 700, y: 640, z: 1.55 },
  ],
  cursor: [
    { f: 200, x: 1500, y: 800 },
    { f: H1.hover, x: 560, y: 660 },
    { f: H1.click, x: 560, y: 660, click: true },
  ],
  callouts: [{ f: 200, to: 290, x: 900, y: 1020, text: "1 credit = RM5 · cost varies by agent", side: "top" }],
  captions: [
    { f: 64, to: 190, text: "Some questions need more than an answer.", detail: "Agents walk you through the whole task, step by step." },
    { f: 196, to: 300, text: "Pay per use — or not at all.", detail: "Many agents are free; others cost 1–3 credits a run." },
    { f: 306, to: 470, text: "Start with money on the table.", detail: "Grant Finder matches your business to government grants." },
  ],
};

// ---------------------------------------------------------------- 2. grant finder
const G2 = { months: 70, revenue: 110, bumi: 160, find: 196, results: 250, draft: 430 };
const GRANTS = [
  { name: "Digital adoption grant", agency: "MDEC", amt: "Up to RM 50,000", when: "Rolling applications", match: 92 },
  { name: "Commercialisation fund", agency: "Cradle", amt: "RM 150,000 – RM 500,000", when: "Closes 30 Nov 2026", match: 84 },
  { name: "Automation matching grant", agency: "SME Corp", amt: "Up to RM 100,000", when: "Closes 15 Jan 2027", match: 71 },
];
const GrantFinder: React.FC = () => {
  const t = useW();
  const tx = useTx();
  const frame = useCurrentFrame();
  const busy = frame >= G2.find && frame < G2.results;
  return (
    <AppShell active="Agents" credits="8 credits">
      <Heading title="Grant Finder" badge="Recommended" sub="Match your business profile to Malaysian government grants — with scoring, near-miss detection, and a recommended application sequence." />
      <Abs x={356} y={330} w={620}>
        <Card style={{ display: "flex", flexDirection: "column", gap: 22 }}>
          <div>
            <Label>{t("Sector")}</Label>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
              {["Technology", "AI", "Fintech", "EdTech", "Manufacturing", "Services"].map((s) => <Chip key={s} on={s === "Technology"} size={18}>{tx(s)}</Chip>)}
            </div>
          </div>
          <div>
            <Label>{t("Business type")}</Label>
            <div style={{ display: "flex", gap: 10 }}>
              {["Sole Proprietor", "Sdn Bhd", "Startup", "LLP"].map((s) => <Chip key={s} on={s === "Sdn Bhd"} size={18}>{tx(s)}</Chip>)}
            </div>
          </div>
          <div style={{ display: "flex", gap: 18 }}>
            <div style={{ flex: 1 }}><Label>{t("Months registered")}</Label><Field value={typed(t("18"), frame, G2.months, 4)} placeholder="e.g. 18" focus={frame >= G2.months - 8 && frame < G2.revenue - 8} /></div>
            <div style={{ flex: 1.3 }}><Label>{t("Annual revenue (yearly, RM)")}</Label><Field value={typed(t("250000"), frame, G2.revenue, 3)} placeholder="e.g. 250000" focus={frame >= G2.revenue - 8 && frame < G2.bumi} /></div>
          </div>
          <div>
            <Label>{t("Bumiputera-owned?")}</Label>
            <div style={{ display: "flex", gap: 10 }}><Chip size={18}>{t("Yes")}</Chip><Chip on={frame >= G2.bumi} size={18}>{t("No")}</Chip></div>
          </div>
          <Button press={G2.find} busy={busy} w="100%">{busy ? "Matching…" : "Find grants"}</Button>
        </Card>
      </Abs>
      {frame >= G2.results && (
        <>
          <Abs x={1010} y={330} w={850}><Rise at={G2.results}><div style={{ fontSize: 26, fontWeight: 800 }}>{t("3 matching grants")}</div></Rise></Abs>
          {GRANTS.map((g, i) => (
            <Abs key={g.name} x={1010} y={380 + i * 172} w={850}>
              <Rise at={G2.results + 6 + i * 8}>
                <Card glow={i === 0} style={{ padding: 22, display: "flex", flexDirection: "column", gap: 10 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <div style={{ fontSize: 25, fontWeight: 800 }}>{tx(g.name)}</div>
                    <Chip on tone={g.match > 80 ? "green" : "amber"} size={17}>{tx(g.match)}{t("% match")}</Chip>
                  </div>
                  <div style={{ display: "flex", gap: 22, fontSize: 19, color: C.mute }}>
                    <span style={{ fontFamily: mono }}>{tx(g.agency)}</span><span>{tx(g.amt)}</span><span>{tx(g.when)}</span>
                  </div>
                  {i === 0 && (
                    <div style={{ display: "flex", gap: 12 }}>
                      <Button size={17} kind="ghost">{t("Apply now →")}</Button>
                      <Button size={17} press={G2.draft}>{t("Draft application →")}</Button>
                    </div>
                  )}
                </Card>
              </Rise>
            </Abs>
          ))}
          <Abs x={1010} y={912} w={850}>
            <Rise at={G2.results + 36}>
              <div style={{ opacity: 0.5, fontSize: 19, padding: "14px 20px", borderRadius: 16, border: `1.5px dashed ${G.border}` }}>{t("Near-miss — close, but doesn't fully qualify yet ·")}{" "}<b>{t("Technology fund")}</b>{" "}{t("needs 24 months registered")}</div>
            </Rise>
          </Abs>
          <DemoFlag />
        </>
      )}
    </AppShell>
  );
};

const ch2: Chapter = {
  name: "Grant Finder",
  title: "Find grants",
  line: "Your profile, matched and ranked.",
  Screen: GrantFinder,
  cam: [
    { f: 0, x: 960, y: 540, z: 1 },
    { f: 60, x: 680, y: 620, z: 1.5 },
    { f: 230, x: 680, y: 640, z: 1.5 },
    { f: 270, x: 1400, y: 600, z: 1.3 },
    { f: 380, x: 1400, y: 560, z: 1.45 },
    { f: 470, x: 1400, y: 560, z: 1.45 },
  ],
  cursor: [
    { f: 50, x: 1000, y: 700 },
    { f: G2.months - 8, x: 540, y: 655, click: true },
    { f: G2.revenue - 8, x: 820, y: 655, click: true },
    { f: G2.bumi, x: 520, y: 760, click: true },
    { f: G2.find, x: 666, y: 845, click: true },
    { f: 380, x: 1500, y: 700 },
    { f: G2.draft, x: 1320, y: 505, click: true },
  ],
  callouts: [
    { f: 290, to: 400, x: 1760, y: 404, text: "Scored against your profile", side: "top", color: "#3DDC97" },
    { f: 330, to: 420, x: 1300, y: 935, text: "Near-miss: what you'd need", side: "bottom" },
  ],
  captions: [
    { f: 64, to: 196, text: "Five quick answers about your business.", detail: "Sector, business type, age, revenue, ownership." },
    { f: 200, to: 330, text: "Every grant you qualify for, ranked.", detail: "Agency, amount, deadline — and the ones you nearly qualify for." },
    { f: 336, to: 470, text: "Found one? Draft the application.", detail: "One click hands it to the Grant Draft Generator." },
  ],
};

// ---------------------------------------------------------------- 3. grant draft generator
const G3 = { gen: 90, review: 120, confirm: 330, ready: 370, dl: 420 };
const STEPS = ["Grant & Business Details", "Review Draft", "Draft Ready"];
const FUNDS = [["Software & cloud", 0.42], ["Staff training", 0.24], ["Hardware", 0.2], ["Consultancy", 0.14]] as const;
const DOCS = ["SSM company profile", "Latest audited accounts", "Quotations from vendors", "Director's MyKad copy"];
const Draft: React.FC = () => {
  const t = useW();
  const tx = useTx();
  const frame = useCurrentFrame();
  const step = frame >= G3.ready ? 2 : frame >= G3.review ? 1 : 0;
  return (
    <AppShell active="Agents" credits={frame >= G3.confirm + 4 ? "5 credits" : "8 credits"}>
      <Heading title="Grant Draft Generator" badge="3 credits" sub="Draft an executive summary, use-of-funds narrative, and document checklist for your selected grant." />
      <Abs x={356} y={300} w={1500}>
        <div style={{ display: "flex", gap: 14 }}>
          {STEPS.map((s, i) => (
            <div key={s} style={{ flex: 1, display: "flex", alignItems: "center", gap: 14, padding: "14px 20px", borderRadius: 16, background: i === step ? "rgba(59,91,255,0.2)" : G.panel, border: `1.5px solid ${i === step ? C.blueHi : G.border}`, fontSize: 21, fontWeight: 700, color: i <= step ? C.white : C.mute }}>
              <div style={{ width: 34, height: 34, borderRadius: 17, display: "flex", alignItems: "center", justifyContent: "center", background: i < step ? G.greenSoft : "rgba(255,255,255,0.08)", fontFamily: mono, fontSize: 17 }}>{i < step ? <Check /> : i + 1}</div>
              {tx(s)}
            </div>
          ))}
        </div>
      </Abs>
      {step === 0 && (
        <Abs x={356} y={400} w={900}>
          <Card style={{ display: "flex", flexDirection: "column", gap: 20 }}>
            <Field value="Digital adoption grant (MDEC)" />
            <div style={{ display: "flex", gap: 16 }}><Field value="Technology" /><Field value="Sdn Bhd" /></div>
            <div style={{ display: "flex", alignItems: "center", gap: 14 }}><Label>{t("Export Format")}</Label><Chip on size={18}>{t("pdf")}</Chip><Chip size={18}>{t("docx")}</Chip></div>
            <Button press={G3.gen} busy={frame >= G3.gen && frame < G3.review}>{t("Generate Draft")}</Button>
          </Card>
        </Abs>
      )}
      {step === 1 && (
        <>
          <Abs x={356} y={400} w={880}>
            <Card style={{ display: "flex", flexDirection: "column", gap: 14, height: 520, boxSizing: "border-box" }}>
              <div style={{ fontFamily: mono, fontSize: 17, letterSpacing: "0.16em", color: C.amber }}>{t("EXECUTIVE SUMMARY")}</div>
              <div style={{ fontSize: 22, lineHeight: 1.55, color: "rgba(244,246,255,0.92)" }}>
                {streamed(t("Our company, a Kuala Lumpur Sdn Bhd registered for 18 months, is applying to digitise its order-to-invoice workflow. The grant will fund cloud software, staff training and a small hardware refresh, cutting manual processing time and letting the team serve more SME customers across the Klang Valley. The project runs for 12 months with quarterly milestones reported to the agency."), frame, G3.review + 8, 1.2)}
              </div>
            </Card>
          </Abs>
          <Abs x={1256} y={400} w={604}>
            <Rise at={G3.review + 30}>
              <Card style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                <div style={{ fontFamily: mono, fontSize: 17, letterSpacing: "0.16em", color: C.amber }}>{t("USE OF FUNDS")}</div>
                {FUNDS.map(([k, v], i) => (
                  <div key={k} style={{ display: "flex", alignItems: "center", gap: 14, fontSize: 19 }}>
                    <span style={{ width: 200 }}>{tx(k)}</span>
                    <div style={{ flex: 1, height: 14, borderRadius: 7, background: "rgba(255,255,255,0.08)" }}>
                      <div style={{ width: `${v * 100 * prog(frame, G3.review + 40 + i * 6, 20)}%`, height: 14, borderRadius: 7, background: `linear-gradient(90deg, ${C.blueHi}, ${C.blue})` }} />
                    </div>
                    <span style={{ fontFamily: mono, width: 50 }}>{Math.round(v * 100)}%</span>
                  </div>
                ))}
              </Card>
            </Rise>
          </Abs>
          <Abs x={1256} y={690} w={604}>
            <Rise at={G3.review + 70}>
              <Card style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                <div style={{ fontFamily: mono, fontSize: 17, letterSpacing: "0.16em", color: C.amber }}>{t("DOCUMENT CHECKLIST")}</div>
                {DOCS.map((d, i) => (
                  <div key={d} style={{ display: "flex", alignItems: "center", gap: 12, fontSize: 19, opacity: prog(frame, G3.review + 80 + i * 8, 10) }}><Check /> {tx(d)}</div>
                ))}
              </Card>
            </Rise>
          </Abs>
          <Abs x={356} y={940} w={1500}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div style={{ fontSize: 18, color: C.mute }}>{t("Financial Projection · Template only — not real figures")}</div>
              <Button press={G3.confirm} busy={frame >= G3.confirm && frame < G3.ready}>{t("Confirm & Generate File")}</Button>
            </div>
          </Abs>
        </>
      )}
      {step === 2 && (
        <Abs x={660} y={420} w={900}>
          <Rise at={G3.ready}>
            <Card glow style={{ display: "flex", alignItems: "center", gap: 30, padding: 40 }}>
              <div style={{ width: 120, height: 150, borderRadius: 14, background: "linear-gradient(160deg, #F4F6FF, #C9D1FF)", display: "flex", alignItems: "flex-end", justifyContent: "center", paddingBottom: 14, fontFamily: mono, fontSize: 22, fontWeight: 700, color: "#E61E25" }}>{t("PDF")}</div>
              <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                <div style={{ fontSize: 34, fontWeight: 800 }}>{t("Draft Ready")}</div>
                <div style={{ fontFamily: mono, fontSize: 20, color: C.mute }}>{t("grant-draft-digital-adoption.pdf")}</div>
                <Button kind="green" press={G3.dl}>{t("Download draft")}</Button>
              </div>
            </Card>
          </Rise>
        </Abs>
      )}
    </AppShell>
  );
};

const ch3: Chapter = {
  name: "Grant Draft",
  title: "Draft it",
  line: "From match to application, reviewed by you.",
  Screen: Draft,
  cam: [
    { f: 0, x: 960, y: 540, z: 1 },
    { f: 60, x: 800, y: 560, z: 1.4 },
    { f: 124, x: 1100, y: 620, z: 1.08 },
    { f: 180, x: 800, y: 620, z: 1.5 },
    { f: 260, x: 1560, y: 660, z: 1.45 },
    { f: 330, x: 1400, y: 900, z: 1.4 },
    { f: 380, x: 1100, y: 560, z: 1.35 },
    { f: 470, x: 1100, y: 560, z: 1.35 },
  ],
  cursor: [
    { f: 50, x: 1100, y: 600 },
    { f: G3.gen, x: 800, y: 700, click: true },
    { f: 300, x: 1500, y: 900 },
    { f: G3.confirm, x: 1700, y: 968, click: true },
    { f: G3.dl, x: 1000, y: 605, click: true },
  ],
  callouts: [
    { f: 60, to: 120, x: 1110, y: 176, text: "3 credits per draft", side: "right" },
    { f: 340, to: 380, x: 1600, y: 48, text: "8 → 5 credits", side: "bottom" },
  ],
  captions: [
    { f: 64, to: 180, text: "The grant and your details carry over.", detail: "Pick PDF or Word, then generate." },
    { f: 186, to: 330, text: "You review every section first.", detail: "Executive summary, use of funds, document checklist." },
    { f: 336, to: 470, text: "Confirm, and the file is ready.", detail: "Nothing is generated until you approve the draft." },
  ],
};

// ---------------------------------------------------------------- 4. patuhiku
const P4 = { focus: 60, type: 70, gen: 190, list: 230, tick1: 330, tick2: 370 };
const FREE_TEXT = "Tech Sdn Bhd, 8 employees, started hiring foreign workers last month, annual revenue RM800k";
const GROUPS: { d: string; items: string[] }[] = [
  { d: "LHDN", items: ["Deduct monthly PCB (MTD) for every employee", "Submit Form E by 31 March"] },
  { d: "EPF · SOCSO · EIS", items: ["Register new foreign workers for EPF contributions", "Enrol foreign workers with SOCSO", "Pay monthly EIS contributions"] },
  { d: "SSM", items: ["File the annual return on time", "Keep company particulars up to date"] },
];
const PatuhiKu: React.FC = () => {
  const t = useW();
  const tx = useTx();
  const frame = useCurrentFrame();
  const done = (frame >= P4.tick2 ? 2 : frame >= P4.tick1 ? 1 : 0) + 1;
  let n = 0;
  return (
    <AppShell active="Agents" credits="5 credits">
      <Heading title="PatuhiKu" badge="1 credit" sub="Cross-references LHDN, EPF/SOCSO/EIS, and SSM compliance obligations for your SME." />
      <Abs x={356} y={310} w={1500}>
        <div style={{ display: "flex", gap: 10 }}><Chip size={19}>{t("Form")}</Chip><Chip on size={19}>{t("Free Text")}</Chip></div>
      </Abs>
      <Abs x={356} y={380} w={1500}>
        <div style={{ display: "flex", gap: 18, alignItems: "stretch" }}>
          <div style={{ flex: 1 }}><Field value={typed(t(FREE_TEXT), frame, P4.type, 1.05)} placeholder="e.g. Tech Sdn Bhd, 8 employees, started hiring foreign workers last month…" focus={frame >= P4.focus && frame < P4.gen} h={76} size={22} /></div>
          <Button press={P4.gen} busy={frame >= P4.gen && frame < P4.list}>{t("Generate checklist")}</Button>
        </div>
      </Abs>
      {frame >= P4.list && (
        <>
          <Abs x={356} y={490} w={1500}>
            <Rise at={P4.list}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div style={{ fontSize: 30, fontWeight: 800 }}>{t("Compliance Checklist")}</div>
                <Chip on tone="green" size={19}>{tx(done)}{" "}{t("of 7 done")}</Chip>
              </div>
            </Rise>
          </Abs>
          {GROUPS.map((g, gi) => (
            <Abs key={g.d} x={356 + gi * 508} y={560} w={484}>
              <Rise at={P4.list + 8 + gi * 8}>
                <Card style={{ padding: 22, display: "flex", flexDirection: "column", gap: 14, height: 400, boxSizing: "border-box" }}>
                  <div style={{ fontFamily: mono, fontSize: 18, letterSpacing: "0.14em", color: C.amber }}>{tx(g.d)}</div>
                  {g.items.map((it) => {
                    const idx = n++;
                    const isDone = idx === 0 || (idx === 2 && frame >= P4.tick1) || (idx === 3 && frame >= P4.tick2);
                    return (
                      <div key={it} style={{ display: "flex", gap: 12, alignItems: "flex-start", fontSize: 20, lineHeight: 1.35, padding: 12, borderRadius: 14, background: isDone ? G.greenSoft : "rgba(255,255,255,0.03)" }}>
                        <div style={{ width: 26, height: 26, flexShrink: 0, borderRadius: 7, border: `2px solid ${isDone ? G.green : G.border}`, display: "flex", alignItems: "center", justifyContent: "center" }}>{isDone && <Check size={16} />}</div>
                        <div style={{ flex: 1 }}>{tx(it)}</div>
                        <span style={{ fontFamily: mono, fontSize: 14, color: isDone ? G.green : C.mute }}>{isDone ? "Done" : "Pending"}</span>
                      </div>
                    );
                  })}
                </Card>
              </Rise>
            </Abs>
          ))}
          <DemoFlag />
        </>
      )}
    </AppShell>
  );
};

const ch4: Chapter = {
  name: "PatuhiKu",
  title: "Stay compliant",
  line: "Every obligation, in one checklist.",
  Screen: PatuhiKu,
  cam: [
    { f: 0, x: 960, y: 540, z: 1 },
    { f: 60, x: 1000, y: 420, z: 1.55 },
    { f: 200, x: 1300, y: 420, z: 1.55 },
    { f: 250, x: 1110, y: 700, z: 1.12 },
    { f: 320, x: 1000, y: 720, z: 1.5 },
    { f: 470, x: 1000, y: 720, z: 1.5 },
  ],
  cursor: [
    { f: 40, x: 1100, y: 700 },
    { f: P4.focus, x: 700, y: 418, click: true },
    { f: P4.gen, x: 1745, y: 418, click: true },
    { f: P4.tick1, x: 880, y: 640, click: true },
    { f: P4.tick2, x: 880, y: 740, click: true },
  ],
  callouts: [{ f: 250, to: 330, x: 1000, y: 632, text: "Triggered by: foreign workers", side: "top" }],
  captions: [
    { f: 64, to: 190, text: "Describe your business like you'd tell a friend.", detail: "Or use the form — headcount, revenue, recent events." },
    { f: 196, to: 320, text: "Your obligations, grouped by agency.", detail: "LHDN, EPF · SOCSO · EIS, and SSM — cross-referenced." },
    { f: 326, to: 470, text: "Tick them off as you go.", detail: "A running count of what's done and what's pending." },
  ],
};

// ---------------------------------------------------------------- 5. deadline monitor
const D5 = { connect: 250, connected: 270, handoff: 330 };
const DEADLINES = [
  { name: "EPF contribution", d: "EPF", due: "15 Oct 2026", f: "Monthly", left: "16 days left", tone: "amber" as const },
  { name: "SOCSO & EIS contribution", d: "PERKESO", due: "15 Oct 2026", f: "Monthly", left: "16 days left", tone: "amber" as const },
  { name: "PCB (MTD) remittance", d: "LHDN", due: "15 Oct 2026", f: "Monthly", left: "16 days left", tone: "amber" as const },
  { name: "SST return", d: "Customs", due: "31 Oct 2026", f: "Bi-monthly", left: "32 days left", tone: "green" as const },
  { name: "Annual return", d: "SSM", due: "30 Nov 2026", f: "Annual", left: "62 days left", tone: "green" as const },
];
const Deadlines: React.FC = () => {
  const t = useW();
  const tx = useTx();
  const frame = useCurrentFrame();
  const handP = prog(frame, D5.handoff, 16);
  return (
    <AppShell active="Agents" credits="5 credits">
      <Heading title="Deadline Monitor" badge="Pro" sub="Regulatory deadline calendar with proactive alerts." />
      {DEADLINES.map((r, i) => (
        <Abs key={r.name} x={356} y={310 + i * 104} w={1000}>
          <Rise at={10 + i * 6}>
            <div style={{ display: "flex", alignItems: "center", gap: 22, height: 88, padding: "0 26px", borderRadius: 18, background: G.panel, border: `1.5px solid ${G.border}` }}>
              <div style={{ width: 70, textAlign: "center", fontFamily: mono, fontSize: 16, lineHeight: 1.2, color: C.mute }}>{r.due.split(" ").slice(0, 2).join(" ")}</div>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 23, fontWeight: 700 }}>{tx(r.name)}</div>
                <div style={{ fontSize: 17, color: C.mute }}>{tx(r.d)} · {tx(r.f)}{" "}{t("· View official source ↗")}</div>
              </div>
              <Chip on tone={r.tone} size={17}>{tx(r.left)}</Chip>
            </div>
          </Rise>
        </Abs>
      ))}
      <Abs x={1400} y={310} w={460}>
        <Rise at={40}>
          <Card style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div style={{ fontSize: 25, fontWeight: 800 }}>{t("Sync to your calendar")}</div>
            {["Google Calendar", "Microsoft Calendar"].map((c, i) => (
              <div key={c} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", fontSize: 20 }}>
                {tx(c)}
                {i === 0 && frame >= D5.connected ? <Chip on tone="green" size={16}>{t("✓ Connected")}</Chip> : <Button size={16} kind="ghost" press={i === 0 ? D5.connect : undefined}>{t("Connect")}</Button>}
              </div>
            ))}
          </Card>
        </Rise>
      </Abs>
      {handP > 0 && (
        <Abs x={1400} y={640} w={460}>
          <div style={{ opacity: handP, translate: `0 ${(1 - handP) * 30}px`, padding: 28, borderRadius: 24, background: "linear-gradient(150deg, rgba(255,178,56,0.2), rgba(59,91,255,0.15))", border: "1.5px solid rgba(255,178,56,0.55)", display: "flex", flexDirection: "column", gap: 12 }}>
            <div style={{ fontFamily: mono, fontSize: 16, letterSpacing: "0.18em", color: C.amber }}>{t("MANAGED SERVICE")}</div>
            <div style={{ fontSize: 28, fontWeight: 800, lineHeight: 1.15 }}>{t("We Handle Your Compliance & Grants")}</div>
            <Button size={18}>{t("Book a Free Call")}</Button>
          </div>
        </Abs>
      )}
      <DemoFlag />
    </AppShell>
  );
};

const ch5: Chapter = {
  name: "Deadlines",
  title: "Never miss one",
  line: "Deadlines that come to you.",
  Screen: Deadlines,
  cam: [
    { f: 0, x: 960, y: 540, z: 1 },
    { f: 60, x: 860, y: 520, z: 1.4 },
    { f: 200, x: 860, y: 620, z: 1.4 },
    { f: 240, x: 1620, y: 420, z: 1.7 },
    { f: 320, x: 1620, y: 420, z: 1.7 },
    { f: 350, x: 1600, y: 700, z: 1.55 },
    { f: 470, x: 1600, y: 700, z: 1.55 },
  ],
  cursor: [
    { f: 200, x: 1200, y: 700 },
    { f: D5.connect, x: 1790, y: 398, click: true },
    { f: 420, x: 1560, y: 868 },
  ],
  callouts: [{ f: 90, to: 200, x: 1350, y: 354, text: "Counts down for you", side: "right" }],
  captions: [
    { f: 64, to: 200, text: "Every filing date, in one calendar.", detail: "EPF, PERKESO, LHDN, Customs, SSM — with the official source." },
    { f: 206, to: 330, text: "Send it to the calendar you already use.", detail: "Google or Microsoft, with alerts before each deadline." },
    { f: 336, to: 470, text: "Rather hand it all off?", detail: "Perniagaan Terurus: we handle your compliance and grants." },
  ],
};

export const BUSINESS: Script = {
  id: "business",
  series: "WALKTHROUGH 02 · RUN YOUR BUSINESS",
  number: "02",
  name: "Run your business",
  tagline: "Grants, filings, deadlines — handled.",
  hook: {
    lines: ["Run the business.", "Not the paperwork."],
    accent: 1,
    chaos: ["SSM annual return due??", "EPF contribution — 15th", "grants_list_v7_FINAL.xlsx", "LHDN Form E", "SST threshold?", "PCB table 2026 (PDF)", "foreign worker EPF rules", "grant FAQ — page 3 of 9"],
  },
  chapters: [ch1, ch2, ch3, ch4, ch5],
  recap: { lines: ["Find.", "Draft.", "Comply."], plan: "PRO — BUSINESS", planDetail: "RM 99/mo per workspace · up to 5 staff" },
  hue: ["59,91,255", "255,150,56"],
  audio: "wt-business.wav",
  drops: [[1280, 1440]],
};

export { display };
