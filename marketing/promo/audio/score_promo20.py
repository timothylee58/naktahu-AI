"""Original score + sound design for NaktahuPromo, frame-synced at 30fps."""
import math
import random
import struct
import wave

SR = 44100
DUR = 20.0
N = int(SR * DUR)
FPS = 30
L = [0.0] * N
R = [0.0] * N
VERB = [0.0] * N  # reverb send (mono)
rnd = random.Random(7)


def at(frame):
    return int(frame / FPS * SR)


def mix(start, samples, gain=1.0, pan=0.0, verb=0.0):
    gl = gain * math.cos((pan + 1) * math.pi / 4) * 1.414
    gr = gain * math.sin((pan + 1) * math.pi / 4) * 1.414
    for i, s in enumerate(samples):
        j = start + i
        if 0 <= j < N:
            L[j] += s * gl
            R[j] += s * gr
            if verb:
                VERB[j] += s * gain * verb


def note(n):
    return 440.0 * 2 ** ((n - 69) / 12)


def lowpass(xs, cut):
    a = 1 - math.exp(-2 * math.pi * cut / SR)
    y, out = 0.0, []
    for x in xs:
        y += a * (x - y)
        out.append(y)
    return out


def noise(n):
    return [rnd.uniform(-1, 1) for _ in range(n)]


# ---------- instruments ----------
def kick():
    n = int(0.38 * SR)
    ph, out = 0.0, []
    for i in range(n):
        t = i / SR
        f = 44 + 110 * math.exp(-t * 32)
        ph += 2 * math.pi * f / SR
        out.append(math.sin(ph) * math.exp(-t * 8.5) + (0.3 * rnd.uniform(-1, 1) * math.exp(-t * 300)))
    return out


def hat(decay=70):
    n = int(0.07 * SR)
    ns = noise(n)
    out, prev = [], 0.0
    for i, x in enumerate(ns):
        hp = x - prev
        prev = x
        out.append(hp * math.exp(-i / SR * decay))
    return out


def snare():
    n = int(0.25 * SR)
    ns = lowpass(noise(n), 5200)
    return [ns[i] * math.exp(-i / SR * 18) * 0.9 + math.sin(2 * math.pi * 185 * i / SR) * math.exp(-i / SR * 30) * 0.5 for i in range(n)]


def bell(freq, dur=1.6, bright=1.0):
    n = int(dur * SR)
    parts = [(1, 1.0, 3.0), (2.0, 0.45 * bright, 5.0), (2.76, 0.3 * bright, 7.5), (5.4, 0.12 * bright, 12.0)]
    out = []
    for i in range(n):
        t = i / SR
        s = sum(a * math.sin(2 * math.pi * freq * m * t) * math.exp(-t * d) for m, a, d in parts)
        out.append(s * min(1, t * 400))
    return out


def click(freq=2600, dur=0.018):
    n = int(dur * SR)
    return [(math.sin(2 * math.pi * freq * i / SR) * 0.6 + rnd.uniform(-1, 1) * 0.4) * math.exp(-i / SR * 260) for i in range(n)]


def pop(f0=720, f1=260, dur=0.09):
    n = int(dur * SR)
    ph, out = 0.0, []
    for i in range(n):
        t = i / SR
        f = f1 + (f0 - f1) * math.exp(-t * 45)
        ph += 2 * math.pi * f / SR
        out.append(math.sin(ph) * math.exp(-t * 38) * min(1, t * 2000))
    return out


def whoosh(dur=0.7, peak=0.55, lo=300, hi=5500, rev=False):
    n = int(dur * SR)
    ns = noise(n)
    out, y = [], 0.0
    for i, x in enumerate(ns):
        p = i / n
        env = (p / peak) ** 2 if p < peak else ((1 - p) / (1 - peak)) ** 1.5
        cut = lo + (hi - lo) * (math.sin(p * math.pi) ** 1.2)
        a = 1 - math.exp(-2 * math.pi * cut / SR)
        y += a * (x - y)
        out.append(y * env)
    return out[::-1] if rev else out


def riser(dur):
    n = int(dur * SR)
    ns = noise(n)
    out, y, ph = [], 0.0, 0.0
    for i, x in enumerate(ns):
        p = i / n
        cut = 200 + 7000 * p ** 2
        a = 1 - math.exp(-2 * math.pi * cut / SR)
        y += a * (x - y)
        ph += 2 * math.pi * (180 + 900 * p ** 2) / SR
        out.append((y * 0.8 + math.sin(ph) * 0.25) * p ** 2.2)
    return out


def impact():
    n = int(2.2 * SR)
    ph, out = 0.0, []
    ns = lowpass(noise(n), 900)
    for i in range(n):
        t = i / SR
        ph += 2 * math.pi * (32 + 50 * math.exp(-t * 6)) / SR
        out.append(math.sin(ph) * math.exp(-t * 2.2) * 1.0 + ns[i] * math.exp(-t * 7) * 1.6)
    return out


# ---------- harmonic bed ----------
# Tension cluster under the chaos, then a four-chord loop once the logo is born.
CHORDS = [
    [50, 57, 62, 64, 69],  # Dmaj9-ish
    [47, 54, 62, 66, 69],  # Bm9
    [43, 55, 59, 62, 66],  # Gmaj7
    [45, 57, 61, 64, 66],  # A6
]


def pad_segment(start_s, dur_s, notes, gain, bright=0.35, attack=0.25, release=0.9):
    n = int((dur_s + release) * SR)
    off = int(start_s * SR)
    for k, m in enumerate(notes):
        f = note(m)
        for det in (-0.12, 0.12):
            ff = f * 2 ** (det / 12)
            ph = rnd.random() * 6.28
            pan = (k / max(1, len(notes) - 1) - 0.5) * 1.2 * (1 if det > 0 else -1)
            buf = []
            for i in range(n):
                t = i / SR
                env = min(1.0, t / attack)
                if t > dur_s:
                    env *= math.exp(-(t - dur_s) * 5 / release)
                ph += 2 * math.pi * ff / SR
                s = math.sin(ph) + bright * math.sin(2 * ph) * 0.5 + bright * 0.25 * math.sin(3 * ph)
                buf.append(s * env)
            mix(off, buf, gain / len(notes), pan, verb=0.35)


# S1 tension: low drone + cluster that swells into the riser
pad_segment(0.0, 2.9, [38, 45, 51, 56], 0.11, bright=0.5, attack=1.2, release=0.3)

# Post-logo loop (bar = 2s = 60 frames), starts on the impact
bar0 = 92 / FPS
t = bar0
k = 0
while t < 19.5:
    dur = min(2.0, 19.9 - t)
    pad_segment(t, dur, CHORDS[k % 4], 0.13 if t < 17.1 else 0.17, bright=0.3, attack=0.08, release=0.8)
    # bass
    f = note(CHORDS[k % 4][0] - 12)
    n = int(dur * SR)
    ph, buf = 0.0, []
    for i in range(n):
        tt = i / SR
        ph += 2 * math.pi * f / SR
        buf.append((math.sin(ph) + 0.3 * math.sin(2 * ph)) * min(1, tt * 60) * (0.7 + 0.3 * math.exp(-tt * 3)))
    if t > 6.2:
        mix(int(t * SR), buf, 0.2)
    t += 2.0
    k += 1

# ---------- drums: 120bpm pulse (every 15 frames) through the product sections ----------
K, H, S_ = kick(), hat(), snare()
beat = 0
f = 197
while f < 580:
    mix(at(f), K, 0.62)
    mix(at(f + 7.5), H, 0.13, pan=0.35)
    if beat % 2 == 1:
        mix(at(f), S_, 0.22, verb=0.25)
    if beat % 4 == 3:
        mix(at(f + 11.25), H, 0.07, pan=-0.4)
    f += 15
    beat += 1

# ---------- S1: chaos ----------
for i in range(24):
    fr = 3 + i * 2.3
    mix(at(fr), click(1800 + rnd.random() * 1600), 0.22 + 0.1 * (i / 24), pan=rnd.uniform(-0.8, 0.8), verb=0.1)
mix(at(24), riser(64 / FPS), 0.5, verb=0.2)
mix(at(56), snare(), 0.3, verb=0.3)  # strike-through hit
mix(at(60), whoosh(0.85, peak=0.9, lo=200, hi=6000), 0.5, pan=0.0)  # suck-in
mix(at(76), bell(note(93), 0.8, 0.4), 0.12, verb=0.4)  # the core ping

# ---------- S2: logo birth (starts f92) ----------
mix(at(92), impact(), 0.95, verb=0.3)
mix(at(94), pop(900, 320, 0.12), 0.35)
for k, fr in enumerate([100, 104, 108, 112]):
    mix(at(fr), click(3200, 0.012), 0.08, pan=-0.2 + k * 0.1)
for k, m in enumerate([74, 78, 81, 85, 86]):  # petals: D-F#-A-C#-D arpeggio
    mix(at(120 + k * 2.5), bell(note(m), 1.8, 0.8), 0.13, pan=-0.4 + k * 0.2, verb=0.5)
mix(at(146), whoosh(0.55, peak=0.4, lo=400, hi=7000), 0.3, pan=0.3)
for k in range(6):
    mix(at(164 + k * 1.2), bell(note(98 + k * 2), 0.5, 0.2), 0.03, pan=-0.5 + k * 0.2, verb=0.6)

# ---------- S3: demo (starts f198) ----------
mix(at(194), whoosh(0.6, peak=0.5), 0.35, pan=-0.3)
fr = 208.0
while fr < 240:
    mix(at(fr), click(1400 + rnd.random() * 900, 0.02), 0.14, pan=0.25)
    fr += 0.9 + rnd.random() * 0.5
mix(at(244), pop(1000, 420, 0.1), 0.45)
for k, m in enumerate([74, 76, 78, 81, 83]):
    mix(at(254 + k * 6), bell(note(m + 12), 0.4, 0.3), 0.07, pan=-0.5 + k * 0.25, verb=0.2)
for k in range(12):
    mix(at(284 + k * 2.7), click(4200, 0.008), 0.05, pan=0.3)
mix(at(316), pop(1300, 600, 0.08), 0.3, pan=0.2)
mix(at(318), whoosh(0.3, peak=0.3, lo=1500, hi=6000), 0.15)
mix(at(322), pop(1500, 700, 0.08), 0.3, pan=0.35)
n = int(0.75 * SR)
ph, buf = 0.0, []
for i in range(n):
    p = i / n
    ph += 2 * math.pi * (600 + 700 * (1 - (1 - p) ** 3)) / SR
    buf.append(math.sin(ph) * math.sin(p * math.pi) * 0.5)
mix(at(320), buf, 0.08, pan=0.4, verb=0.3)
mix(at(342), bell(note(86), 1.2, 0.6), 0.1, verb=0.4)

# ---------- S4: agents (starts f346) ----------
mix(at(342), whoosh(0.7, peak=0.45, lo=300, hi=7000), 0.45, pan=0.6)
for k in range(5):
    mix(at(356 + k * 3), whoosh(0.22, peak=0.3, lo=800, hi=5000), 0.12, pan=-0.6 + k * 0.3)
mix(at(422), click(1200, 0.03), 0.4)
mix(at(423), pop(600, 900, 0.14), 0.25)
mix(at(426), bell(note(81), 1.2, 0.7), 0.1, verb=0.4)

# ---------- S5: trust (starts f440) ----------
mix(at(438), whoosh(0.6, peak=0.5, lo=250, hi=4000), 0.3)
mix(at(444), impact()[: int(1.2 * SR)], 0.35, verb=0.3)
for k in range(6):
    mix(at(446 + k * 3), pop(800 + k * 90, 400, 0.07), 0.14, pan=-0.7 + k * 0.28)
mix(at(464), bell(note(90), 1.4, 0.7), 0.12, verb=0.5)
mix(at(484), click(2400, 0.02), 0.15)
mix(at(506), click(2600, 0.02), 0.15)

# ---------- S6: end card (starts f516) ----------
mix(at(512), whoosh(0.7, peak=0.6, lo=200, hi=6000), 0.35)
for k, m in enumerate([62, 69, 74, 78, 81, 85]):
    mix(at(520 + k * 1.5), bell(note(m), 2.6, 0.7), 0.1, pan=-0.5 + k * 0.2, verb=0.5)
for k in range(8):
    mix(at(560 + k * 1.3), bell(note(100 + (k % 4) * 3), 0.45, 0.2), 0.035, pan=-0.6 + k * 0.17, verb=0.6)

# ---------- reverb: 4 combs + 2 allpass (Schroeder) ----------
def comb(x, d, g):
    y = [0.0] * len(x)
    for i in range(len(x)):
        y[i] = x[i] + (g * y[i - d] if i >= d else 0.0)
    return y


def allpass(x, d, g):
    y = [0.0] * len(x)
    for i in range(len(x)):
        xd = x[i - d] if i >= d else 0.0
        yd = y[i - d] if i >= d else 0.0
        y[i] = -g * x[i] + xd + g * yd
    return y


wet = [0.0] * N
for d, g in ((1557, 0.84), (1617, 0.83), (1491, 0.85), (1422, 0.84)):
    c = comb(VERB, d, g)
    for i in range(N):
        wet[i] += c[i] * 0.25
wet = allpass(allpass(wet, 225, 0.5), 556, 0.5)
wetR = [0.0] * 23 + wet[:-23]
for i in range(N):
    L[i] += wet[i] * 0.55
    R[i] += wetR[i] * 0.55

# ---------- master ----------
peak = max(max(abs(x) for x in L), max(abs(x) for x in R))
g = 0.95 / peak * 1.6
fade_in, fade_out = int(0.05 * SR), int(0.4 * SR)
frames = bytearray()
for i in range(N):
    e = min(1.0, i / fade_in) * min(1.0, (N - i) / fade_out)
    l = math.tanh(L[i] * g) * e * 0.93
    r = math.tanh(R[i] * g) * e * 0.93
    frames += struct.pack("<hh", int(l * 32767), int(r * 32767))
with wave.open("public/score.wav", "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(bytes(frames))
print("wrote public/score.wav")
