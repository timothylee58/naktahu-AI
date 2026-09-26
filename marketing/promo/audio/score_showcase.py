"""Upbeat score for the NakTahu feature showcase.

128.57 BPM = exactly 14 frames per beat at 30fps (1 frame = 1600 samples at 48kHz),
so every visual cut can sit on the grid. 20 bars = 1120 frames; the video is 1140.

Bar map (frames = bar * 56): see the harmony section.
"""
import json
import sys
import wave

import numpy as np
from scipy.signal import butter, fftconvolve, lfilter

SR = 48000
FPS = 30
SPF = SR // FPS  # 1600 samples per frame
BEAT = 14
BAR = 56
TOTAL_FRAMES = 1140
N = TOTAL_FRAMES * SPF
PAD = SR * 3
rng = np.random.default_rng(11)

music = np.zeros((2, N + PAD))
send = np.zeros((2, N + PAD))  # reverb send
kick_times: list[int] = []


def fs(frame: float) -> int:
    return int(round(frame * SPF))


def mtof(m: float) -> float:
    return 440.0 * 2 ** ((m - 69) / 12)


def pan_gains(pan: float):
    return np.cos((pan + 1) * np.pi / 4) * np.sqrt(2), np.sin((pan + 1) * np.pi / 4) * np.sqrt(2)


def add(sig, start: int, gain=1.0, pan=0.0, verb=0.0, bus=None):
    bus = music if bus is None else bus
    if sig.ndim == 1:
        gl, gr = pan_gains(pan)
        st = np.vstack([sig * gl, sig * gr])
    else:
        st = sig
    end = min(bus.shape[1], start + st.shape[1])
    if end <= start or start < 0:
        return
    bus[:, start:end] += st[:, : end - start] * gain
    if verb:
        send[:, start:end] += st[:, : end - start] * gain * verb


# ---------------- DSP helpers ----------------
def lp(x, fc, order=2):
    b, a = butter(order, min(0.99, fc / (SR / 2)), "low")
    return lfilter(b, a, x)


def hp(x, fc, order=2):
    b, a = butter(order, min(0.99, fc / (SR / 2)), "high")
    return lfilter(b, a, x)


def bp(x, lo, hi, order=2):
    b, a = butter(order, [lo / (SR / 2), min(0.99, hi / (SR / 2))], "band")
    return lfilter(b, a, x)


def sweep_lp(x, f0, f1, curve=1.0, chunk=256):
    out = np.zeros_like(x)
    zi = np.zeros(2)
    n = len(x)
    for s in range(0, n, chunk):
        p = (s / max(1, n - 1)) ** curve
        fc = f0 * (f1 / f0) ** p
        b, a = butter(2, min(0.99, fc / (SR / 2)))
        y, zi = lfilter(b, a, x[s : s + chunk], zi=zi)
        out[s : s + chunk] = y
    return out


TBL = 4096
_tables: dict[int, np.ndarray] = {}


def saw_table(f):
    nh = int(max(1, min(160, 17000 / f)))
    if nh not in _tables:
        x = np.arange(TBL) / TBL
        tbl = np.zeros(TBL)
        for k in range(1, nh + 1):
            tbl += np.sinc(k / (nh + 1)) * np.sin(2 * np.pi * k * x) / k
        _tables[nh] = tbl * (2 / np.pi)
    return _tables[nh]


def saw(f, n, phase=0.0):
    tbl = saw_table(f)
    idx = ((phase + f * np.arange(n) / SR) % 1.0) * TBL
    i0 = idx.astype(np.int64)
    fr = idx - i0
    return tbl[i0] * (1 - fr) + tbl[(i0 + 1) % TBL] * fr


def square(f, n, phase=0.0):
    return saw(f, n, phase) - saw(f, n, phase + 0.5)


def env_adsr(n, a, d, s, r, gate):
    t = np.arange(n) / SR
    e = np.where(t < a, t / max(a, 1e-4), s + (1 - s) * np.exp(-(t - a) / max(d, 1e-4)))
    gate_t = gate / SR
    rel = np.where(t > gate_t, np.exp(-(t - gate_t) / max(r, 1e-4)), 1.0)
    return e * rel


# ---------------- instruments ----------------
def kick(n_sec=0.42):
    n = int(n_sec * SR)
    t = np.arange(n) / SR
    f = 46 + 160 * np.exp(-t * 36)
    ph = 2 * np.pi * np.cumsum(f) / SR
    body = np.sin(ph) * np.exp(-t * 8.5) * np.minimum(1, t * 800)
    click = hp(rng.uniform(-1, 1, n), 2500) * np.exp(-t * 420) * 0.5
    return np.tanh((body + click) * 1.6) * 0.9


def clap():
    n = int(0.5 * SR)
    t = np.arange(n) / SR
    nz = bp(rng.uniform(-1, 1, n), 900, 3800)
    e = np.zeros(n)
    for off in (0.0, 0.009, 0.019, 0.028):
        tt = t - off
        e += np.where(tt >= 0, np.exp(-np.maximum(tt, 0) * (90 if off < 0.02 else 13)), 0)
    return nz * e * 0.9


def hat_closed():
    n = int(0.07 * SR)
    t = np.arange(n) / SR
    return hp(rng.uniform(-1, 1, n), 7500, 3) * np.exp(-t * 60)


def hat_open():
    n = int(0.32 * SR)
    t = np.arange(n) / SR
    return hp(rng.uniform(-1, 1, n), 6200, 3) * np.exp(-t * 9) * np.minimum(1, t * 3000)


def snare():
    n = int(0.22 * SR)
    t = np.arange(n) / SR
    nz = bp(rng.uniform(-1, 1, n), 1400, 9000) * np.exp(-t * 24)
    tone = np.sin(2 * np.pi * 205 * t) * np.exp(-t * 38) * 0.6
    return nz + tone


def snap():
    n = int(0.09 * SR)
    t = np.arange(n) / SR
    return bp(rng.uniform(-1, 1, n), 1800, 6000) * np.exp(-t * 85)


def crash(sec=2.2):
    n = int(sec * SR)
    t = np.arange(n) / SR
    nz = hp(rng.uniform(-1, 1, (2, n)), 3500, 2)
    nz = np.vstack([lp(nz[0], 13000), lp(nz[1], 13000)])
    return nz * (np.exp(-t * 2.2) * np.minimum(1, t * 2000))


def riser(sec):
    n = int(sec * SR)
    t = np.arange(n) / SR
    p = t / sec
    nz = sweep_lp(rng.uniform(-1, 1, n), 300, 9000, curve=1.6)
    f = 220 * (8 ** (p ** 1.4))
    tone = np.sin(2 * np.pi * np.cumsum(f) / SR)
    return (nz * 0.8 + tone * 0.18) * p ** 2.4


def rev_cymbal(sec):
    c = crash(sec + 0.3)[:, : int(sec * SR)]
    return c[:, ::-1] * np.linspace(0, 1, c.shape[1]) ** 1.5


def impact():
    n = int(2.0 * SR)
    t = np.arange(n) / SR
    f = 30 + 55 * np.exp(-t * 5)
    sub = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 2.4)
    body = lp(rng.uniform(-1, 1, n), 700) * np.exp(-t * 9) * 1.4
    return np.tanh((sub + body) * 1.3)


def supersaw_chord(notes, n, gate, cutoff, amp=1.0, spread=0.9, a=0.004, r=0.12):
    out = np.zeros((2, n))
    detunes = [-19, -12, -6, 0, 6, 12, 19]
    for m in notes:
        for j, c in enumerate(detunes):
            f = mtof(m) * 2 ** (c / 1200)
            v = saw(f, n, rng.random())
            pan = (j / (len(detunes) - 1) - 0.5) * 2 * spread
            gl, gr = pan_gains(pan)
            out[0] += v * gl
            out[1] += v * gr
    out /= len(detunes) * max(1, len(notes)) ** 0.5
    if callable(cutoff):
        out = np.vstack([cutoff(out[0]), cutoff(out[1])])
    else:
        out = np.vstack([lp(out[0], cutoff), lp(out[1], cutoff)])
    return out * env_adsr(n, a, 0.3, 0.85, r, gate) * amp


def pluck(notes, n_sec=0.34, bright=5200):
    n = int(n_sec * SR)
    t = np.arange(n) / SR
    v = np.zeros(n)
    for m in notes:
        f = mtof(m)
        v += saw(f, n, rng.random()) * 0.6 + square(f * 2, n, rng.random()) * 0.15
    cut = np.exp(-t * 18)
    y = lp(v, bright) * (0.35 + 0.65 * cut)
    return y * np.exp(-t * 9) * np.minimum(1, t * 1500) / max(1, len(notes)) ** 0.5


def lead_note(m, dur_sec, vib=True):
    n = int((dur_sec + 0.25) * SR)
    t = np.arange(n) / SR
    f = mtof(m)
    vibr = 1 + (0.004 * np.sin(2 * np.pi * 5.5 * t) * np.clip((t - 0.18) * 4, 0, 1) if vib else 0)
    ph1 = np.cumsum(f * vibr * 2 ** (7 / 1200)) / SR
    ph2 = np.cumsum(f * vibr * 2 ** (-7 / 1200)) / SR
    tbl = saw_table(f)
    def rd(ph):
        idx = (ph % 1.0) * TBL
        i0 = idx.astype(np.int64)
        fr = idx - i0
        return tbl[i0] * (1 - fr) + tbl[(i0 + 1) % TBL] * fr
    v = rd(ph1) + rd(ph2) + 0.35 * np.sin(2 * np.pi * np.cumsum(f * vibr / 2) / SR)
    v = lp(v, 6500) + lp(v, 10000) * 0.3 * np.exp(-t * 14)
    return v * env_adsr(n, 0.004, 0.16, 0.62, 0.09, int(dur_sec * SR)) * 0.5


def arp_note(m):
    n = int(0.22 * SR)
    t = np.arange(n) / SR
    f = mtof(m)
    v = square(f, n, rng.random()) * 0.5 + saw(f * 2, n) * 0.25
    return lp(v, 6500) * np.exp(-t * 16) * np.minimum(1, t * 2500)


def bass_note(m, dur_sec):
    n = int((dur_sec + 0.05) * SR)
    t = np.arange(n) / SR
    f = mtof(m)
    body = saw(f, n) * 0.55 + square(f, n) * 0.25
    body = lp(body, 1150) + lp(body, 3200) * 0.4 * np.exp(-t * 30)
    sub = np.sin(2 * np.pi * f * t) * 0.45
    return np.tanh((body + sub) * 1.4) * env_adsr(n, 0.003, 0.08, 0.8, 0.03, int(dur_sec * SR))


# ---------------- harmony ----------------
# 20 bars. 0-1 intro, 2-8 drop 1, 9 break, 10-16 drop 2, 17 build, 18 final drop, 19 resolve.
CHORDS = ["F#m", "D", "F#m", "D", "A", "E", "F#m", "D", "A", "Bm",
          "F#m", "D", "A", "E", "F#m", "D", "A", "E", "F#m", "A"]
NBARS = len(CHORDS)
VOICE = {"F#m": [57, 61, 66], "D": [57, 62, 66], "A": [57, 61, 64], "E": [56, 59, 64], "Bm": [59, 62, 66]}
ROOT = {"F#m": 42, "D": 38, "A": 45, "E": 40, "Bm": 47}
# lead motifs on a 16-step bar: (step, midi, length_steps)
MOTIF = {
    "F#m": [(0, 73, 2), (3, 73, 1), (4, 76, 2), (6, 78, 3), (10, 76, 2), (12, 73, 2), (14, 71, 2)],
    "D": [(0, 74, 2), (3, 73, 1), (4, 71, 2), (6, 69, 4), (12, 66, 2), (14, 69, 2)],
    "A": [(0, 73, 2), (3, 76, 1), (4, 81, 3), (8, 80, 2), (10, 76, 2), (12, 73, 4)],
    "E": [(0, 71, 2), (3, 68, 1), (4, 71, 2), (6, 76, 2), (8, 80, 4), (12, 78, 2), (14, 76, 2)],
}
STEP = BEAT / 4  # 3.5 frames per 16th
SYNC = [0, 3, 6, 10, 13]  # syncopated pluck stab steps

DROP1 = list(range(2, 9))
DROP2 = list(range(10, 17))
FULL = set(DROP1) | set(DROP2) | {18}
BREAK, BUILD, END = 9, 17, 19


def bar_f(b):
    return b * BAR


K, CL, HC, HO, SN, SNP = kick(), clap(), hat_closed(), hat_open(), snare(), snap()


def groove_bar(b, beats=range(4), shaker=False):
    f0 = bar_f(b)
    for bt in beats:
        fr = f0 + bt * BEAT
        add(K, fs(fr), 0.8)
        kick_times.append(fs(fr))
        if bt in (1, 3):
            add(CL, fs(fr), 0.62, pan=0.05, verb=0.3)
        add(HO, fs(fr + 2 * STEP), 0.26, pan=-0.2)
        for s in (1, 3):
            add(HC, fs(fr + s * STEP), 0.17 + 0.05 * (s == 3), pan=0.3)
    if shaker:
        for s in range(16):
            if s // 4 in beats:
                add(HC, fs(f0 + s * STEP), 0.075, pan=-0.45)


for b in range(NBARS):
    f0 = bar_f(b)
    if b == 0:
        for bt in (1, 3):
            add(SNP, fs(f0 + bt * BEAT), 0.55, pan=0.15, verb=0.3)
        for s in range(0, 16, 2):
            add(HC, fs(f0 + s * STEP), 0.07 + 0.03 * (s % 4 == 2), pan=0.25)
    elif b == 1:
        for bt in range(4):
            add(lp(K, 900), fs(f0 + bt * BEAT), 0.7)
            kick_times.append(fs(f0 + bt * BEAT))
        for bt in (1, 3):
            add(CL, fs(f0 + bt * BEAT), 0.3, verb=0.35)
    elif b in FULL:
        groove_bar(b, shaker=(b in DROP2 or b == 18))
    elif b == BREAK:
        for bt in (1, 3):
            add(CL, fs(f0 + bt * BEAT), 0.42, verb=0.5)
        for s in range(0, 16, 2):
            add(HC, fs(f0 + s * STEP), 0.08, pan=0.25)
    elif b == BUILD:
        groove_bar(b, beats=range(3), shaker=True)  # beat 4 is the gap before the final drop


def roll(start_f, end_f, g0=0.08, g1=0.42):
    fr = start_f
    k = 0
    while fr < end_f - 2:
        p = (fr - start_f) / (end_f - start_f)
        add(SN, fs(fr), g0 + (g1 - g0) * p ** 1.3, pan=0.1 * np.sin(k), verb=0.25)
        step = STEP * 2 if p < 0.4 else (STEP if p < 0.75 else STEP / 2)
        fr += step
        k += 1


roll(bar_f(1) + 2 * BEAT, bar_f(2) - 3)
roll(bar_f(BREAK) + 2 * BEAT, bar_f(BREAK + 1) - 3)
roll(bar_f(BUILD), bar_f(BUILD + 1) - 3, 0.06, 0.45)

for bar_end in (2, BREAK + 1, BUILD + 1):
    sec = BAR / FPS
    add(riser(sec), fs(bar_f(bar_end) - BAR), 0.22, verb=0.2)
    add(rev_cymbal(0.47), fs(bar_f(bar_end)) - int(0.47 * SR), 0.2)

for fr, g in ((bar_f(2), 1.0), (bar_f(10), 1.0), (bar_f(18), 1.0), (bar_f(END), 1.1)):
    add(crash(), fs(fr), 0.3 * g, verb=0.3)
    add(impact(), fs(fr), 0.5 * g, verb=0.15)
add(K, fs(bar_f(END)), 1.0)

# sidechain envelope from every kick
sc = np.ones(N + PAD)
shape_n = int(0.36 * SR)
tt = np.arange(shape_n) / SR
duck = 1 - 0.78 * np.exp(-tt / 0.085) * np.minimum(1, tt / 0.004 + 0.3)
for k0 in kick_times:
    e = min(N + PAD, k0 + shape_n)
    sc[k0:e] = np.minimum(sc[k0:e], duck[: e - k0])

# chords (sidechained bus)
pads = np.zeros((2, N + PAD))
nbar = BAR * SPF
for b in range(NBARS):
    notes = VOICE[CHORDS[b]]
    f0 = fs(bar_f(b))
    if b == 0:
        sig = supersaw_chord(notes, nbar, nbar - 400, lambda x: sweep_lp(x, 300, 1500, curve=1.2), amp=2.3)
    elif b == 1:
        sig = supersaw_chord(notes, nbar, nbar - 400, lambda x: sweep_lp(x, 350, 4200, curve=1.8), amp=0.9)
    elif b == BREAK:
        sig = supersaw_chord(notes + [notes[1] + 12], nbar, nbar - 1800, lambda x: sweep_lp(x, 900, 2600, curve=1.5), amp=1.35)
    elif b == BUILD:
        sig = supersaw_chord(notes + [notes[1] + 12], nbar, nbar - 300, lambda x: sweep_lp(x, 1400, 8000, curve=1.4), amp=1.1)
    elif b == END:
        n = int(2.9 * SR)
        sig = supersaw_chord(notes + [notes[0] + 12, notes[2] + 12], n, int(0.9 * SR), lambda x: sweep_lp(x, 6500, 900, curve=0.7), amp=1.25, r=0.8)
    else:
        extra = [notes[1] + 12] if (b in DROP2 or b == 18) else []
        sig = supersaw_chord(notes + extra, nbar, nbar - 300, 5200, amp=1.0)
    add(sig, f0, 1.0, bus=pads)
add(pads * sc, 0, 0.3, verb=0.25)

# plucks: syncopated stabs (intro filtered, drops bright)
for b in [0, 1] + sorted(FULL):
    for s in SYNC:
        bright = 2400 if b == 0 else (3400 if b == 1 else 8500)
        p = pluck([n + 12 for n in VOICE[CHORDS[b]]], bright=bright)
        add(p, fs(bar_f(b) + s * STEP), 0.3 if b >= 2 else 0.62, pan=0.4 if s % 2 else -0.4, verb=0.25)

# arp (16ths, chord tones up an octave)
pattern = [0, 1, 2, 1, 2, 3, 2, 1]
for b in [0, 1, BREAK] + DROP2 + [BUILD, 18]:
    tones = [n + 12 for n in VOICE[CHORDS[b]]] + [VOICE[CHORDS[b]][0] + 24]
    for s in range(16):
        g = 0.1 if b in (0, 1) else (0.24 if b == BREAK else (0.12 if b == BUILD else 0.08))
        add(arp_note(tones[pattern[s % 8]]), fs(bar_f(b) + s * STEP), g, pan=0.55 * (1 if s % 2 else -1), verb=0.35)

# bass: offbeat 8ths (+ octave pops in drop 2)
for b in sorted(FULL) + [BUILD]:
    root = ROOT[CHORDS[b]]
    for bt in range(4):
        if b == BUILD and bt == 3:
            continue
        fr = bar_f(b) + bt * BEAT + 2 * STEP
        add(bass_note(root, 0.19), fs(fr), 0.42)
        if (b in DROP2 or b == 18) and bt in (1, 3):
            add(bass_note(root + 12, 0.08), fs(fr + STEP), 0.16)
add(lp(bass_note(ROOT["Bm"] - 12, 1.7), 400), fs(bar_f(BREAK)), 0.26)
add(bass_note(45, 1.6), fs(bar_f(END)), 0.45)

# lead hook with ping-pong delay
lead = np.zeros((2, N + PAD))
for b in DROP1[1:] + DROP2 + [18]:
    ch = CHORDS[b]
    for step, m, ln in MOTIF[ch]:
        add(lead_note(m, ln * STEP / FPS), fs(bar_f(b) + step * STEP), 0.5, bus=lead)
        if b in DROP2 or b == 18:
            add(lead_note(m + 12, ln * STEP / FPS), fs(bar_f(b) + step * STEP), 0.16, bus=lead)
add(lead_note(81, 1.4), fs(bar_f(END)), 0.5, bus=lead)
dl = int(3 * STEP * SPF)
wet = np.zeros_like(lead)
for k in range(1, 5):
    seg = lead[0] + lead[1]
    wet[k % 2, dl * k :] += seg[: -dl * k] * (0.34 ** k) * 0.5
add(lead, 0, 0.55, verb=0.2)
add(np.vstack([lp(wet[0], 4000), lp(wet[1], 4000)]), 0, 0.5)

# ---------------- UI sound design (quiet, on top of the music) ----------------
def ui_click(freq=2600, sec=0.02):
    n = int(sec * SR)
    t = np.arange(n) / SR
    return (np.sin(2 * np.pi * freq * t) * 0.6 + rng.uniform(-1, 1, n) * 0.4) * np.exp(-t * 240)


def ui_pop(f0=900, f1=320, sec=0.1):
    n = int(sec * SR)
    t = np.arange(n) / SR
    f = f1 + (f0 - f1) * np.exp(-t * 45)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 34) * np.minimum(1, t * 2500)


def ui_whoosh(sec=0.4):
    n = int(sec * SR)
    p = np.linspace(0, 1, n)
    x = sweep_lp(rng.uniform(-1, 1, n), 600, 7000, curve=1.0)
    return x * np.sin(p * np.pi) ** 2


def ui_bell(m, sec=1.0):
    n = int(sec * SR)
    t = np.arange(n) / SR
    f = mtof(m)
    return sum(a * np.sin(2 * np.pi * f * k * t) * np.exp(-t * d) for k, a, d in ((1, 1, 4), (2, 0.4, 7), (2.76, 0.25, 10))) * np.minimum(1, t * 800)


SFX = json.load(open(sys.argv[1])) if len(sys.argv) > 1 else []
for ev in SFX:
    kind, fr = ev["kind"], ev["frame"]
    g = ev.get("gain", 1.0)
    pan = ev.get("pan", 0.0)
    if kind == "click":
        add(ui_click(ev.get("freq", 2600)), fs(fr), 0.16 * g, pan)
    elif kind == "key":
        add(ui_click(1500 + rng.random() * 800, 0.018), fs(fr), 0.1 * g, pan)
    elif kind == "pop":
        add(ui_pop(ev.get("f0", 900), ev.get("f1", 320)), fs(fr), 0.22 * g, pan, verb=0.1)
    elif kind == "whoosh":
        add(ui_whoosh(ev.get("sec", 0.4)), fs(fr), 0.18 * g, pan)
    elif kind == "bell":
        add(ui_bell(ev.get("note", 81)), fs(fr), 0.07 * g, pan, verb=0.4)

# ---------------- reverb + master ----------------
ir_n = int(1.9 * SR)
t = np.arange(ir_n) / SR
irenv = np.exp(-6.9 * t / 1.9)
pre = int(0.018 * SR)
ir = [np.concatenate([np.zeros(pre), lp(rng.standard_normal(ir_n) * irenv, 7500)]) for _ in range(2)]
ir = [x / np.sqrt(np.sum(x ** 2)) * 0.9 for x in ir]
verb = np.vstack([fftconvolve(send[0], ir[0])[: N + PAD], fftconvolve(send[1], ir[1])[: N + PAD]])
mix = music + np.vstack([hp(verb[0], 180), hp(verb[1], 180)]) * 0.55

mix = mix[:, :N]
mix = np.vstack([hp(mix[0], 28), hp(mix[1], 28)])
mix = mix + np.vstack([hp(mix[0], 4200), hp(mix[1], 4200)]) * 0.28  # air shelf
mix = mix + np.vstack([bp(mix[0], 1700, 5200), bp(mix[1], 1700, 5200)]) * 0.6  # presence for phone speakers
drive = 1.8
mix = np.tanh(mix * drive / np.max(np.abs(mix)) * 1.2) / np.tanh(1.2 * drive)
mix *= 0.93 / np.max(np.abs(mix))
fade = int(0.35 * SR)
mix[:, -fade:] *= np.linspace(1, 0, fade) ** 2

pcm = (np.clip(mix.T, -1, 1) * 32767).astype(np.int16)
out = sys.argv[2] if len(sys.argv) > 2 else "public/showcase.wav"
with wave.open(out, "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(pcm.tobytes())

# per-bar loudness report
for b in range(NBARS):
    seg = mix[:, fs(bar_f(b)) : fs(bar_f(b + 1))]
    rms = np.sqrt(np.mean(seg ** 2))
    print(f"bar {b:2d} {CHORDS[b]:>4}  rms {20 * np.log10(rms + 1e-9):6.1f} dB  peak {np.max(np.abs(seg)):.2f}")
print("wrote", out)
