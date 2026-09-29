import React from "react";
import { useCurrentFrame } from "remotion";
import { C, mono, prog, streamed, typed } from "./engine";
import { Abs, AppShell, Button, Card, Check, Chip, DemoFlag, Field, G, Heading, Label, Rise, Spinner } from "./ui";
import type { Chapter, Script } from "./Walkthrough";

/**
 * Walkthrough 03 — Life moments. The civic agents for the big, stressful
 * moments: feeling unwell, moving for work, making ends meet, losing a job,
 * sitting SPM. Labels are the product's real strings; results are
 * illustrative and flagged on screen as demo data.
 */

const Group: React.FC<{ label: string; opts: string[]; on: (o: string) => boolean; size?: number }> = ({ label, opts, on, size = 18 }) => (
  <div>
    <Label>{label}</Label>
    <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
      {opts.map((o) => <Chip key={o} on={on(o)} size={size}>{o}</Chip>)}
    </div>
  </div>
);

// ---------------------------------------------------------------- 1. health triage
const H = { head: 70, fever: 104, headache: 124, days: 164, moderate: 198, go: 240, result: 280, pdf: 420 };
const Triage: React.FC = () => {
  const frame = useCurrentFrame();
  return (
    <AppShell active="Agents">
      <Heading title="Health Triage" badge="Free" tone="green" sub="BM symptom intake → KKM guidance → clinic/hospital recommendation." />
      <Abs x={356} y={300} w={1500}>
        <div style={{ display: "flex", alignItems: "center", gap: 14, padding: "14px 24px", borderRadius: 16, background: "rgba(230,30,37,0.2)", border: "1.5px solid rgba(255,107,111,0.6)", fontSize: 22, fontWeight: 800 }}>🚨 Emergency? Call 999 now</div>
      </Abs>
      <Abs x={356} y={390} w={720}>
        <Card style={{ display: "flex", flexDirection: "column", gap: 22 }}>
          <Group label="Where do you feel it?" opts={["General", "Head", "Chest", "Abdomen", "Skin"]} on={(o) => o === "Head" && frame >= H.head} />
          <Group label="Symptoms" opts={["Fever", "Cough", "Headache", "Dizziness", "Nausea / Vomiting"]} on={(o) => (o === "Fever" && frame >= H.fever) || (o === "Headache" && frame >= H.headache)} />
          <Group label="How long?" opts={["< 1 day", "1–3 days", "3–7 days", "> 1 week"]} on={(o) => o === "1–3 days" && frame >= H.days} />
          <Group label="How bad?" opts={["🟢 Mild", "🟡 Moderate", "Severe"]} on={(o) => o === "🟡 Moderate" && frame >= H.moderate} />
          <Button press={H.go} busy={frame >= H.go && frame < H.result} w="100%">Get guidance</Button>
        </Card>
      </Abs>
      {frame >= H.result && (
        <Abs x={1110} y={390} w={750}>
          <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
            <Rise at={H.result}>
              <div style={{ padding: 26, borderRadius: 22, background: "rgba(255,178,56,0.16)", border: "1.5px solid rgba(255,178,56,0.6)" }}>
                <div style={{ fontSize: 28, fontWeight: 800 }}>🟡 See a doctor within 24 hours</div>
                <div style={{ fontSize: 20, color: "rgba(244,246,255,0.85)", marginTop: 8, lineHeight: 1.4 }}>A klinik kesihatan or GP can check a fever with headache. Go to A&amp;E if it gets worse.</div>
              </div>
            </Rise>
            <Rise at={H.result + 12}>
              <Card style={{ padding: 22, display: "flex", flexDirection: "column", gap: 12 }}>
                <div style={{ fontFamily: mono, fontSize: 16, letterSpacing: "0.16em", color: C.amber }}>NEARBY FACILITIES</div>
                {["Klinik Kesihatan · 1.2 km", "Klinik Kesihatan · 3.4 km"].map((f) => (
                  <div key={f} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 20 }}>{f}<Chip size={16}>Get directions</Chip></div>
                ))}
              </Card>
            </Rise>
            <Rise at={H.result + 22}><Button kind="ghost" press={H.pdf}>Download summary (PDF)</Button></Rise>
          </div>
          <DemoFlag />
        </Abs>
      )}
    </AppShell>
  );
};

const ch1: Chapter = {
  name: "Health Triage",
  title: "Feeling unwell",
  line: "Where to go, and how soon.",
  Screen: Triage,
  cam: [
    { f: 0, x: 960, y: 540, z: 1 },
    { f: 60, x: 720, y: 620, z: 1.5 },
    { f: 250, x: 720, y: 700, z: 1.5 },
    { f: 290, x: 1400, y: 600, z: 1.45 },
    { f: 470, x: 1400, y: 640, z: 1.45 },
  ],
  cursor: [
    { f: 50, x: 1000, y: 600 },
    { f: H.head, x: 578, y: 488, click: true },
    { f: H.fever, x: 420, y: 578, click: true },
    { f: H.headache, x: 624, y: 578, click: true },
    { f: H.days, x: 562, y: 668, click: true },
    { f: H.moderate, x: 560, y: 758, click: true },
    { f: H.go, x: 716, y: 840, click: true },
    { f: H.pdf, x: 1260, y: 780, click: true },
  ],
  callouts: [{ f: 70, to: 200, x: 700, y: 322, text: "Emergencies come first", side: "right", color: "#FF6B6F" }],
  captions: [
    { f: 64, to: 236, text: "Tap through what you're feeling.", detail: "Body area, symptoms, how long, how bad." },
    { f: 240, to: 380, text: "Clear guidance, grounded in KKM advice.", detail: "Plus the nearest facilities and directions." },
    { f: 386, to: 470, text: "Take the summary with you.", detail: "A PDF to show the doctor." },
  ],
};

// ---------------------------------------------------------------- 2. immigration navigator
const I = { work: 90, type: 120, cont: 196, yes: 262, result: 300 };
const INTENTS = ["Work in Malaysia", "Study in Malaysia", "Visit", "Start a Business", "Extend My Visa", "Submit MDAC", "Renew ePLKS", "PVIP"];
const IMM_TEXT = "I'm from Mainland China, want to work in KL for 2 years";
const Immigration: React.FC = () => {
  const frame = useCurrentFrame();
  const chat = frame >= I.work + 10;
  return (
    <AppShell active="Agents" credits="3 credits">
      <Heading title="Immigration Navigator" badge="1 credit" tone="amber" sub="Answer a few quick questions about your visit → get a document checklist, warnings, and official references." />
      {!chat &&
        INTENTS.map((t, i) => (
          <Abs key={t} x={356 + (i % 4) * 380} y={330 + Math.floor(i / 4) * 170} w={360} h={150}>
            <Rise at={8 + i * 3}>
              <div style={{ height: 150, boxSizing: "border-box", padding: 24, borderRadius: 22, background: i === 0 && frame >= I.work - 20 ? "rgba(59,91,255,0.2)" : G.panel, border: `1.5px solid ${i === 0 && frame >= I.work - 20 ? C.blueHi : G.border}`, fontSize: 25, fontWeight: 800, display: "flex", alignItems: "flex-end" }}>{t}</div>
            </Rise>
          </Abs>
        ))}
      {chat && (
        <>
          <Abs x={356} y={320} w={900}>
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              <Rise at={I.work + 10}><div style={{ alignSelf: "flex-start", maxWidth: 820, padding: "18px 24px", borderRadius: "22px 22px 22px 6px", background: G.panelHi, fontSize: 22 }}>Tell me about your plans — where are you from, and how long will you stay?</div></Rise>
              {frame >= I.cont && <Rise at={I.cont}><div style={{ display: "flex", justifyContent: "flex-end" }}><div style={{ padding: "18px 24px", borderRadius: "22px 22px 6px 22px", background: C.blue, fontSize: 22, fontWeight: 600 }}>{IMM_TEXT}</div></div></Rise>}
              {frame >= I.cont + 20 && <Rise at={I.cont + 20}><div style={{ alignSelf: "flex-start", padding: "18px 24px", borderRadius: "22px 22px 22px 6px", background: G.panelHi, fontSize: 22 }}>Do you already have a job offer from a Malaysian employer?</div></Rise>}
              {frame >= I.cont + 30 && frame < I.result && (
                <Rise at={I.cont + 30}><div style={{ display: "flex", gap: 10 }}>{["Yes", "No", "I need more details", "What documents do I need?"].map((q) => <Chip key={q} on={q === "Yes" && frame >= I.yes} size={18}>{q}</Chip>)}</div></Rise>
              )}
            </div>
          </Abs>
          {frame < I.cont && (
            <Abs x={356} y={900} w={900}>
              <div style={{ display: "flex", gap: 14 }}><div style={{ flex: 1 }}><Field value={typed(IMM_TEXT, frame, I.type, 1.2)} placeholder="Type your answer…" focus={frame >= I.type - 6} /></div><Button press={I.cont}>Continue</Button></div>
            </Abs>
          )}
          {frame >= I.result && (
            <Abs x={1290} y={320} w={570}>
              <Rise at={I.result}>
                <Card glow style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                  <div style={{ fontSize: 22, color: C.mute }}>Here's your visa type and document checklist.</div>
                  <div style={{ fontSize: 32, fontWeight: 800 }}>Employment Pass</div>
                  {["Passport with enough validity", "Employer's job offer letter", "Academic certificates", "Passport photo"].map((d, i) => (
                    <div key={d} style={{ display: "flex", gap: 12, alignItems: "center", fontSize: 20, opacity: prog(frame, I.result + 10 + i * 6, 10) }}><Check /> {d}</div>
                  ))}
                  <div style={{ display: "flex", gap: 10, marginTop: 6 }}><Button size={17}>Open Official Portal</Button><Button size={17} kind="ghost">SPO Enquiry Draft</Button></div>
                </Card>
              </Rise>
              <DemoFlag />
            </Abs>
          )}
        </>
      )}
    </AppShell>
  );
};

const ch2: Chapter = {
  name: "Immigration",
  title: "Moving here",
  line: "The right visa, and every document for it.",
  Screen: Immigration,
  cam: [
    { f: 0, x: 960, y: 540, z: 1 },
    { f: 60, x: 900, y: 480, z: 1.35 },
    { f: 110, x: 820, y: 560, z: 1.4 },
    { f: 250, x: 820, y: 560, z: 1.4 },
    { f: 310, x: 1300, y: 560, z: 1.3 },
    { f: 400, x: 1560, y: 560, z: 1.5 },
    { f: 470, x: 1560, y: 560, z: 1.5 },
  ],
  cursor: [
    { f: 50, x: 1100, y: 700 },
    { f: I.work, x: 520, y: 420, click: true },
    { f: I.type - 6, x: 700, y: 932, click: true },
    { f: I.cont, x: 1180, y: 932, click: true },
    { f: I.yes, x: 390, y: 538, click: true },
    { f: 440, x: 1500, y: 800 },
  ],
  callouts: [{ f: 360, to: 460, x: 1500, y: 740, text: "Straight to the official portal", side: "bottom" }],
  captions: [
    { f: 64, to: 190, text: "Pick what you're trying to do.", detail: "Work, study, visit, start a business, extend a visa…" },
    { f: 196, to: 300, text: "It asks what matters, one step at a time.", detail: "In plain language, with quick replies." },
    { f: 306, to: 470, text: "Leave with the visa type and a checklist.", detail: "Plus official references and a ready-to-send enquiry." },
  ],
};

// ---------------------------------------------------------------- 3. check assistance
const A = { fill: 64, check: 200, result: 240 };
const FIELDS: [string, string][] = [
  ["Birth Year", "1988"], ["State of Residence", "Selangor"], ["Marital Status", "Married"],
  ["Household income (RM)", "3,800"], ["Dependent children", "3"], ["Employment", "Private sector"],
];
const SCHEMES = [
  { name: "Sumbangan Tunai Rahmah (STR)", cat: "Cash aid", agency: "LHDN", why: "Household income and children within the STR bands" },
  { name: "Sumbangan Asas Rahmah (SARA)", cat: "Essentials credit", agency: "MOF", why: "You're already an STR household" },
  { name: "Bantuan Awal Persekolahan", cat: "Education", agency: "KPM", why: "You have school-age children" },
];
const Assistance: React.FC = () => {
  const frame = useCurrentFrame();
  return (
    <AppShell active="Agents">
      <Heading title="Check Assistance" badge="Free" tone="green" sub="Match your household profile to cost-of-living assistance schemes (Ihsan MADANI and similar)." />
      <Abs x={356} y={310} w={640}>
        <Card style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <div style={{ display: "flex", gap: 10 }}>{["Demographics", "Household", "Status"].map((s, i) => <Chip key={s} on={i === 0} size={17}>{s}</Chip>)}</div>
          {FIELDS.map(([k, v], i) => (
            <div key={k} style={{ display: "flex", alignItems: "center", gap: 14 }}>
              <div style={{ width: 250, fontSize: 19, color: C.mute }}>{k}</div>
              <div style={{ flex: 1 }}><Field value={frame >= A.fill + i * 18 ? v : ""} h={52} size={20} focus={frame >= A.fill + i * 18 - 6 && frame < A.fill + (i + 1) * 18 - 6} caret={false} /></div>
            </div>
          ))}
          <Button press={A.check} busy={frame >= A.check && frame < A.result} w="100%">Check Eligibility</Button>
        </Card>
      </Abs>
      {frame >= A.result && (
        <Abs x={1030} y={310} w={830}>
          <Rise at={A.result}><div style={{ fontSize: 28, fontWeight: 800, marginBottom: 16 }}>3 matching schemes</div></Rise>
          {SCHEMES.map((s, i) => (
            <Rise key={s.name} at={A.result + 8 + i * 10} style={{ marginBottom: 16 }}>
              <Card glow={i === 0} style={{ padding: 22, display: "flex", flexDirection: "column", gap: 8 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div style={{ fontSize: 24, fontWeight: 800 }}>{s.name}</div>
                  <span style={{ fontFamily: mono, fontSize: 17, color: C.mute }}>{s.agency}</span>
                </div>
                <div style={{ fontSize: 18, color: G.green }}>Why you qualify · <span style={{ color: "rgba(244,246,255,0.85)" }}>{s.why}</span></div>
                <div style={{ display: "flex", gap: 10 }}><Chip size={15}>{s.cat}</Chip><Chip size={15}>View official source ↗</Chip></div>
              </Card>
            </Rise>
          ))}
          <DemoFlag />
        </Abs>
      )}
    </AppShell>
  );
};

const ch3: Chapter = {
  name: "Check Assistance",
  title: "Making ends meet",
  line: "Aid you qualify for — and why.",
  Screen: Assistance,
  cam: [
    { f: 0, x: 960, y: 540, z: 1 },
    { f: 60, x: 680, y: 620, z: 1.5 },
    { f: 210, x: 680, y: 700, z: 1.5 },
    { f: 250, x: 1440, y: 580, z: 1.35 },
    { f: 360, x: 1440, y: 470, z: 1.6 },
    { f: 470, x: 1440, y: 470, z: 1.6 },
  ],
  cursor: [
    { f: 50, x: 1000, y: 700 },
    { f: A.fill, x: 800, y: 420 },
    { f: A.fill + 90, x: 800, y: 740 },
    { f: A.check, x: 676, y: 870, click: true },
    { f: 380, x: 1600, y: 520 },
  ],
  callouts: [{ f: 360, to: 460, x: 1200, y: 460, text: "Reason shown for every match", side: "bottom", color: "#3DDC97" }],
  captions: [
    { f: 64, to: 196, text: "Tell it about your household.", detail: "Age, state, income, dependents, work." },
    { f: 202, to: 340, text: "Every scheme you match, in one list.", detail: "STR, SARA and more — with the agency that runs each one." },
    { f: 346, to: 470, text: "Never a mystery why.", detail: "Each match says why you qualify, and links the official source." },
  ],
};

// ---------------------------------------------------------------- 4. retrenchment navigator
const R = { type: 70, start: 150, result: 190 };
const RET_TEXT = "I worked 3 years, salary RM4,500, given 14 days notice";
const RETS = [
  { h: "Estimated Statutory Termination Benefit", big: "≈ RM 7,788", note: "15 days' wages × 3 years of service", tone: C.white },
  { h: "EIS Claim Eligibility", big: "Check with PERKESO", note: "If you contributed to EIS, claim within 60 days", tone: C.amber },
  { h: "Notice Period Status", big: "28 days short", note: "6 weeks' notice for 2–5 years' service", tone: C.amber },
];
const Retrenchment: React.FC = () => {
  const frame = useCurrentFrame();
  return (
    <AppShell active="Agents">
      <Heading title="Retrenchment Navigator" badge="Free" tone="green" sub="EIS claim eligibility, statutory termination benefits, and a next-steps checklist." />
      <Abs x={356} y={310} w={1500}>
        <div style={{ display: "flex", gap: 16 }}>
          <div style={{ flex: 1 }}><Field value={typed(RET_TEXT, frame, R.type, 1.2)} placeholder="I worked 3 years, salary RM4,500, given 14 days notice…" focus={frame >= R.type - 8 && frame < R.start} h={76} /></div>
          <Button press={R.start} busy={frame >= R.start && frame < R.result}>Start</Button>
        </div>
      </Abs>
      {frame >= R.result && (
        <>
          {RETS.map((r, i) => (
            <Abs key={r.h} x={356 + i * 508} y={430} w={484}>
              <Rise at={R.result + i * 10}>
                <Card style={{ height: 250, boxSizing: "border-box", display: "flex", flexDirection: "column", gap: 14 }}>
                  <div style={{ fontFamily: mono, fontSize: 16, letterSpacing: "0.12em", color: C.mute }}>{r.h.toUpperCase()}</div>
                  <div style={{ fontSize: 44, fontWeight: 800, letterSpacing: "-0.03em", color: r.tone }}>{r.big}</div>
                  <div style={{ fontSize: 19, color: "rgba(244,246,255,0.8)", lineHeight: 1.4 }}>{r.note}</div>
                </Card>
              </Rise>
            </Abs>
          ))}
          <Abs x={356} y={710} w={1500}>
            <Rise at={R.result + 40}>
              <Card style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                <div style={{ fontFamily: mono, fontSize: 16, letterSpacing: "0.16em", color: C.amber }}>CHECKLIST</div>
                {["Ask your employer for the termination letter in writing", "File your EIS claim with PERKESO", "Request your final payslip and EA form", "Check your EPF statement is up to date"].map((c, i) => (
                  <div key={c} style={{ display: "flex", gap: 12, alignItems: "center", fontSize: 20, opacity: prog(frame, R.result + 50 + i * 8, 10) }}><Check /> {c}</div>
                ))}
              </Card>
            </Rise>
          </Abs>
          <DemoFlag />
        </>
      )}
    </AppShell>
  );
};

const ch4: Chapter = {
  name: "Retrenchment",
  title: "Losing a job",
  line: "What you're owed, and what to do next.",
  Screen: Retrenchment,
  cam: [
    { f: 0, x: 960, y: 540, z: 1 },
    { f: 60, x: 1000, y: 350, z: 1.55 },
    { f: 170, x: 1100, y: 350, z: 1.55 },
    { f: 210, x: 1110, y: 560, z: 1.15 },
    { f: 280, x: 600, y: 560, z: 1.7 },
    { f: 340, x: 1110, y: 560, z: 1.7 },
    { f: 400, x: 1110, y: 820, z: 1.45 },
    { f: 470, x: 1110, y: 820, z: 1.45 },
  ],
  cursor: [
    { f: 50, x: 1100, y: 600 },
    { f: R.type - 8, x: 800, y: 348, click: true },
    { f: R.start, x: 1800, y: 348, click: true },
    { f: 300, x: 700, y: 620 },
    { f: 440, x: 900, y: 900 },
  ],
  captions: [
    { f: 64, to: 190, text: "Describe what happened, in one line.", detail: "Years of service, salary, notice given." },
    { f: 196, to: 390, text: "What you're owed, worked out.", detail: "Termination benefit, notice period, and where EIS fits in." },
    { f: 396, to: 470, text: "Then, what to do next.", detail: "A checklist, in order." },
  ],
};

// ---------------------------------------------------------------- 5. study agent
const S = { drop: 70, extract: 130, explained: 170, quiz: 290, gen: 320, score: 360 };
const QS = [
  { q: "Soalan 1 · Nyatakan dua faktor kemunculan nasionalisme di Tanah Melayu.", t: "Nasionalisme" },
  { q: "Soalan 2 · Apakah tujuan penubuhan Persekutuan Tanah Melayu 1948?", t: "Persekutuan 1948" },
  { q: "Soalan 3 · Terangkan peranan Suruhanjaya Reid.", t: "Kemerdekaan" },
];
const Study: React.FC = () => {
  const frame = useCurrentFrame();
  const quiz = frame >= S.quiz;
  const dropP = prog(frame, S.drop - 20, 20);
  return (
    <AppShell active="Agents" credits="Student">
      <Heading title="Study Agent" badge="Student" tone="blue" sub="Upload your SPM past paper — get an explanation for every question and see which topics to focus on." />
      <Abs x={356} y={300} w={560}>
        <Card style={{ display: "flex", flexDirection: "column", gap: 18 }}>
          <Group label="Level" opts={["SPM", "STPM", "A-Level"]} on={(o) => o === "SPM"} />
          <Group label="Subject" opts={["Sejarah", "Matematik", "Sains", "BM", "BI"]} on={(o) => o === "Sejarah"} />
          <Group label="Mode" opts={["Explain", "Quiz"]} on={(o) => (o === "Quiz") === quiz} />
          <div style={{ display: "flex", gap: 10 }}>{["Paste text", "Upload PDF", "Scan photo"].map((t) => <Chip key={t} on={t === "Upload PDF"} size={16}>{t}</Chip>)}</div>
          <div style={{ height: 110, borderRadius: 18, border: `2px dashed ${frame >= S.drop ? C.blueHi : G.border}`, display: "flex", alignItems: "center", justifyContent: "center", gap: 14, fontSize: 19, color: C.mute }}>
            {frame >= S.drop ? (
              <><div style={{ padding: "8px 12px", borderRadius: 10, background: "#F4F6FF", color: "#E61E25", fontFamily: mono, fontWeight: 700, fontSize: 15 }}>PDF</div><span style={{ color: C.white, fontWeight: 700 }}>sejarah_spm_k1.pdf</span></>
            ) : "Drop your past paper here"}
          </div>
          <Button press={quiz ? S.gen : S.extract} busy={(frame >= S.extract && frame < S.explained) || (frame >= S.gen && frame < S.score)} w="100%">{quiz ? "Generate quiz" : "Extract & explain"}</Button>
        </Card>
      </Abs>
      {/* the file flying in */}
      {dropP > 0 && dropP < 1 && (
        <Abs x={1400 - 900 * dropP} y={200 + 540 * dropP} w={120}>
          <div style={{ padding: "18px 14px", borderRadius: 12, background: "#F4F6FF", color: "#E61E25", fontFamily: mono, fontWeight: 700, fontSize: 20, rotate: `${(1 - dropP) * 14}deg`, boxShadow: "0 20px 40px rgba(0,0,0,0.4)" }}>PDF</div>
        </Abs>
      )}
      {frame >= S.explained && !quiz && (
        <Abs x={950} y={300} w={910}>
          <Rise at={S.explained}><div style={{ fontSize: 28, fontWeight: 800, marginBottom: 14 }}>Explanations</div></Rise>
          {QS.map((q, i) => (
            <Rise key={q.q} at={S.explained + 8 + i * 12} style={{ marginBottom: 14 }}>
              <Card style={{ padding: 20, display: "flex", flexDirection: "column", gap: 8 }}>
                <div style={{ fontSize: 20, fontWeight: 700 }}>{q.q}</div>
                <div style={{ fontSize: 18, color: "rgba(244,246,255,0.8)", lineHeight: 1.4 }}>{i === 0 ? streamed("Jawapan: pengaruh pendidikan dan akhbar, serta kesan Perang Dunia Kedua. Kata kunci: kesedaran, penentangan.", frame, S.explained + 12, 1) : "…"}</div>
                <Chip size={14}>Topic · {q.t}</Chip>
              </Card>
            </Rise>
          ))}
        </Abs>
      )}
      {quiz && frame >= S.score && (
        <Abs x={950} y={300} w={910}>
          <Rise at={S.score}>
            <Card glow style={{ display: "flex", alignItems: "center", gap: 30, padding: 32 }}>
              <div style={{ fontSize: 90, fontWeight: 800, letterSpacing: "-0.05em" }}>8<span style={{ color: C.mute, fontSize: 60 }}>/10</span></div>
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                <div style={{ fontSize: 26, fontWeight: 800 }}>Score: 8/10</div>
                <div style={{ display: "flex", gap: 10 }}><Chip on tone="green" size={16}>Correct · 7</Chip><Chip on tone="amber" size={16}>Partially correct · 2</Chip><Chip on tone="red" size={16}>Not quite · 1</Chip></div>
              </div>
            </Card>
          </Rise>
          <Rise at={S.score + 20}>
            <div style={{ marginTop: 20, fontSize: 21, color: C.mute }}>Focus next: <b style={{ color: C.white }}>Kemerdekaan</b> — revise the Reid Commission.</div>
          </Rise>
        </Abs>
      )}
      <DemoFlag />
    </AppShell>
  );
};

const ch5: Chapter = {
  name: "Study Agent",
  title: "Sitting SPM",
  line: "Past papers, explained. Then tested.",
  Screen: Study,
  cam: [
    { f: 0, x: 960, y: 540, z: 1 },
    { f: 60, x: 800, y: 560, z: 1.25 },
    { f: 150, x: 700, y: 700, z: 1.45 },
    { f: 190, x: 1300, y: 540, z: 1.35 },
    { f: 280, x: 1300, y: 540, z: 1.35 },
    { f: 310, x: 650, y: 560, z: 1.5 },
    { f: 370, x: 1400, y: 440, z: 1.55 },
    { f: 470, x: 1400, y: 440, z: 1.55 },
  ],
  cursor: [
    { f: 40, x: 1400, y: 240 },
    { f: S.drop, x: 640, y: 780 },
    { f: S.extract, x: 636, y: 880, click: true },
    { f: S.quiz, x: 530, y: 580, click: true },
    { f: S.gen, x: 636, y: 880, click: true },
    { f: 440, x: 1300, y: 600 },
  ],
  captions: [
    { f: 64, to: 170, text: "Drop in a past paper.", detail: "Paste it, upload the PDF, or scan a photo." },
    { f: 176, to: 290, text: "Every question, explained.", detail: "With the topic it tests, so you know what to revise." },
    { f: 296, to: 470, text: "Then test yourself.", detail: "A quiz, a score, and what to focus on next." },
  ],
};

export const LIFE: Script = {
  id: "life",
  series: "WALKTHROUGH 03 · LIFE MOMENTS",
  number: "03",
  name: "Life moments",
  tagline: "The big moments, made simpler.",
  hook: {
    lines: ["Life happens.", "Paperwork follows."],
    accent: 1,
    chaos: ["klinik near me open now", "work visa malaysia 2026", "am I eligible for STR?", "retrenchment benefit calculator", "EIS claim — how long?", "SPM sejarah past year", "lost MyKad what to do", "SOCSO form which one"],
  },
  chapters: [ch1, ch2, ch3, ch4, ch5],
  recap: { lines: ["Guided.", "Grounded.", "Free."], plan: "FREE CIVIC TOOLS", planDetail: "Health Triage, Check Assistance, Retrenchment Navigator" },
  hue: ["59,91,255", "61,200,151"],
  audio: "wt-life.wav",
  drops: [[1280, 1440]],
};

export { Spinner };
