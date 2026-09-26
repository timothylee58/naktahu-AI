""""Park Bench" boom-bap score for the feature showcase.

Built from the Park Bench spec: Fm7 - Dbmaj7 - Bbm7 - C7alt with Rhodes (2:1 FM
tine) voicings, kick on 1 and the "and" of 3, snare on 2 and 4. Tempo is 85.71 BPM
rather than 84 so a beat is exactly 21 frames at 30fps; one bar = 84 frames = one scene.
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
TOTAL_FRAMES = 1696
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


# ---------------- boom-bap instruments ----------------
def bb_kick():
    n = int(0.5 * SR)
    t = np.arange(n) / SR
    f = 48 + 90 * np.exp(-t * 28)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 7) * np.minimum(1, t * 900)
    knock = bp(rng.uniform(-1, 1, n), 900, 3200) * np.exp(-t * 90) * 0.5
    return np.tanh((body + knock) * 2.2) * 0.8


def bb_snare(ghost=False):
    n = int(0.42 * SR)
    t = np.arange(n) / SR
    crack = bp(rng.uniform(-1, 1, n), 1500, 7000) * np.exp(-t * (40 if ghost else 16))
    body = np.sin(2 * np.pi * 190 * t) * np.exp(-t * 30) * 0.8
    room = lp(rng.uniform(-1, 1, n), 3000) * np.exp(-t * 7) * 0.25
    return np.tanh((crack + body + room) * 1.6) * (0.35 if ghost else 1.0)


def bb_hat(open_=False):
    n = int((0.25 if open_ else 0.06) * SR)
    t = np.arange(n) / SR
    return hp(rng.uniform(-1, 1, n), 7000, 3) * np.exp(-t * (11 if open_ else 70))


def rhodes(notes, dur):
    """Tine electric piano: FM bell attack over a warm sine body, with slow tremolo."""
    n = int((dur + 0.6) * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    for m in notes:
        f = mtof(m)
        mod = 1.2 * np.sin(2 * np.pi * f * 2 * t) * np.exp(-t * 3.5) + 0.5 * np.sin(2 * np.pi * f * 14 * t) * np.exp(-t * 12)
        tine = np.sin(2 * np.pi * f * t + mod)
        body = np.sin(2 * np.pi * f * t) + 0.25 * np.sin(2 * np.pi * 2 * f * t)
        out += (tine * 0.45 + body * 0.55) * np.exp(-t * 0.9)
    trem = 1 + 0.12 * np.sin(2 * np.pi * 4.2 * t)
    gate = np.where(t > dur, np.exp(-(t - dur) * 8), 1.0)
    return lp(out * trem * gate * np.minimum(1, t * 600), 5500) / len(notes) ** 0.5


FORMANTS = {"ah": (730, 1090, 2440), "oh": (570, 840, 2410), "oo": (300, 870, 2240)}


def choir(notes, dur, vowel="ah"):
    """Soul vocal chop stand-in: detuned saws through vowel formant filters, tape-warped."""
    n = int((dur + 0.4) * SR)
    t = np.arange(n) / SR
    src = np.zeros(n)
    for m in notes:
        for c in (-9, 0, 9):
            src += saw(mtof(m) * 2 ** (c / 1200), n, rng.random())
    f1, f2, f3 = FORMANTS[vowel]
    y = bp(src, f1 * 0.8, f1 * 1.25) + 0.7 * bp(src, f2 * 0.85, f2 * 1.2) + 0.25 * bp(src, f3 * 0.9, f3 * 1.1)
    env = np.minimum(1, t / 0.08) * np.where(t > dur, np.exp(-(t - dur) * 7), 1.0)
    return y * env / (3 * len(notes)) ** 0.5


def upright(m, dur):
    n = int((dur + 0.1) * SR)
    t = np.arange(n) / SR
    f = mtof(m)
    pluck_ = np.sin(2 * np.pi * f * t) + 0.35 * np.sin(2 * np.pi * 2 * f * t) * np.exp(-t * 6)
    thump = lp(rng.uniform(-1, 1, n), 400) * np.exp(-t * 40) * 0.6
    env = np.exp(-t * 1.8) * np.minimum(1, t * 400) * np.where(t > dur, np.exp(-(t - dur) * 20), 1.0)
    return np.tanh((pluck_ + thump) * env * 1.3)


def flute(m, dur):
    n = int((dur + 0.2) * SR)
    t = np.arange(n) / SR
    f = mtof(m) * (1 + 0.006 * np.sin(2 * np.pi * 5.2 * t) * np.clip(t * 3 - 0.3, 0, 1))
    ph = 2 * np.pi * np.cumsum(f) / SR
    tone = np.sin(ph) + 0.18 * np.sin(2 * ph)
    breath = bp(rng.uniform(-1, 1, n), mtof(m) * 1.5, mtof(m) * 4) * 0.12
    env = np.minimum(1, t / 0.06) * np.where(t > dur, np.exp(-(t - dur) * 12), 1.0)
    return (tone + breath) * env


# ---------------- arrangement: 64.29 BPM half-time boom-bap ----------------
# One beat = 28 frames, one bar = 112 frames = two visual scenes, so every scene cut
# lands on the kick (beat 1) or the snare (beat 3).
HB = 21
HBAR = 84
STEP16 = HB / 4
SWING = 0.62  # late 16ths, the MPC feel
NBARS = TOTAL_FRAMES // HBAR + 1
PROG = [  # (bass roots, Rhodes voicing) straight from the Park Bench spec
    ([41], [53, 60, 63, 68, 72]),  # Fm7
    ([37], [49, 56, 60, 65, 68]),  # Dbmaj7
    ([34], [46, 53, 56, 61, 65]),  # Bbm7
    ([36], [48, 56, 58, 64, 63]),  # C7alt
]
CHORDS = ["Fm7", "Dbmaj7", "Bbm7", "C7alt"] * 6
DROP_OUT = (9 * 84, 10 * 84)  # drums out for the "12 agents" breakdown scene
END = 19 * 84


def bar_f(b):
    return b * HBAR


def swung(step):
    base = step * STEP16
    return base + (SWING - 0.5) * 2 * STEP16 if step % 2 else base


def drums_on(fr):
    return HBAR <= fr < END and not (DROP_OUT[0] <= fr < DROP_OUT[1])


K, SN, GH, HC, HO = bb_kick(), bb_snare(), bb_snare(True), bb_hat(), bb_hat(True)
KICKS = [0, 10]  # steps in a 16-step bar (beat 1, "and-a" of beat 3)
for b in range(NBARS):
    f0 = bar_f(b)
    for s in range(16):
        fr = f0 + swung(s)
        if not drums_on(fr):
            continue
        if s in KICKS or (s == 7 and b % 2):
            add(K, fs(fr), 0.9)
            kick_times.append(fs(fr))
        if s in (4, 12):
            add(SN, fs(fr), 0.75, pan=0.05, verb=0.25)
        if s in (7, 15) and b % 2 == 0:
            add(GH, fs(fr), 0.5, pan=-0.1)
        if s % 2 == 0 or s in (11, 15):
            vel = 0.2 if s % 4 == 0 else 0.13
            add(HO if s == 14 and b % 2 else HC, fs(fr), vel, pan=0.3)

sc = np.ones(N + PAD)
duck_n = int(0.3 * SR)
duck = 1 - 0.35 * np.exp(-np.arange(duck_n) / SR / 0.09)
for k0 in kick_times:
    e = min(N + PAD, k0 + duck_n)
    sc[k0:e] = np.minimum(sc[k0:e], duck[: e - k0])

keys = np.zeros((2, N + PAD))
for b in range(NBARS):
    roots, voicing = PROG[b % 4]
    f0 = bar_f(b)
    if f0 >= TOTAL_FRAMES:
        break
    dur = HBAR / FPS
    add(rhodes(voicing, dur * 0.7), fs(f0), 1.0, pan=-0.15, bus=keys)
    add(rhodes(voicing[2:], dur * 0.25), fs(f0 + swung(10)), 0.55, pan=-0.15, bus=keys)
    for i, r in enumerate(roots):
        span = HBAR / len(roots)
        if drums_on(f0 + i * span) or b == 0:
            add(upright(r, 0.55), fs(f0 + i * span), 0.55)
            add(upright(r + 7 if r < 40 else r - 5, 0.25), fs(f0 + i * span + swung(6)), 0.35)
    if f0 >= 2 * HBAR and f0 < END and b != 9:
        add(choir([voicing[1] + 12, voicing[3] + 12], dur * 0.45, "ah" if b % 2 else "oh"), fs(f0 + HB * 2), 0.5, pan=0.3, verb=0.4, bus=keys)
# intro and breakdown: keys through a low-pass, like a sample before the drums drop
keys[:, : fs(HBAR)] = np.vstack([lp(keys[0, : fs(HBAR)], 900), lp(keys[1, : fs(HBAR)], 900)])
a, b_ = fs(DROP_OUT[0]), fs(DROP_OUT[1])
keys[:, a:b_] = np.vstack([lp(keys[0, a:b_], 1400), lp(keys[1, a:b_], 1400)])
add(keys * sc, 0, 0.55, verb=0.2)

# flute hook on the second half of each 4-bar phrase
HOOK = [(0, 72, 3), (4, 75, 2), (7, 77, 5), (14, 75, 2), (16, 72, 4), (22, 70, 6)]
for b in (3, 7, 11, 15):
    for step, m, ln in HOOK:
        add(flute(m, ln * STEP16 / FPS), fs(bar_f(b) + swung(step % 16) + (step // 16) * HBAR / 1), 0.18, pan=0.2, verb=0.45)

# vinyl crackle + tape hiss across the whole track
crack = np.zeros(N + PAD)
pops = rng.integers(0, N, 1400)
crack[pops] = rng.uniform(-1, 1, len(pops)) * rng.uniform(0.2, 1, len(pops))
crack = hp(crack, 1500) + lp(rng.standard_normal(N + PAD), 6000) * 0.01
add(crack, 0, 0.07)

# final chord rings out on the end card
add(rhodes([53, 60, 63, 68, 72], 2.6), fs(END), 0.9, verb=0.4)
add(upright(29 + 12, 1.5), fs(END), 0.6)
add(K, fs(END), 0.8)

# gentle tape wow on the music bus
t_all = np.arange(N + PAD) / SR
wow = (0.0016 * np.sin(2 * np.pi * 0.55 * t_all) * SR).astype(np.int64)
idx = np.clip(np.arange(N + PAD) - wow - 80, 0, N + PAD - 1)
music[:] = music[:, idx]

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
