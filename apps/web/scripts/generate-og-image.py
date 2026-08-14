#!/usr/bin/env python3
"""Generate the OpenGraph share card (public/og-image.png).

One-off design tool, NOT part of the build — run manually when the brand
changes. Needs Pillow (`pip install Pillow`); it is deliberately not a
project dependency, since the output is a committed static asset.

    python3 apps/web/scripts/generate-og-image.py

Design notes: the agency row is set in IBM Plex Mono inside double-ruled
chips, deliberately echoing the citation "stamp" the product renders on
every sourced answer — the share card advertises the actual differentiator
rather than a generic tagline. The agencies named are the real corpus
sources (see apps/api/scripts/sources.py); nothing here implies government
endorsement, and no crest or seal is used.
"""
from PIL import Image, ImageDraw, ImageFont
import pathlib, math

W, H, SS = 1200, 630, 2
INK, BLUE, AMBER, WHITE = (0x14,0x16,0x2B), (0x3B,0x5B,0xFF), (0xFF,0xB2,0x38), (0xED,0xEA,0xE3)
MUTED = (0x8A,0x8F,0x98)

ROOT = pathlib.Path(__file__).resolve().parents[3]
FONTS = ROOT/".agents/skills/canvas-design/canvas-fonts"
def font(name, size):
    return ImageFont.truetype(str(FONTS/name), size*SS)

img = Image.new("RGB", (W*SS, H*SS), INK)
d = ImageDraw.Draw(img, "RGBA")

# Soft blue bloom, top-left — mirrors the landing hero's radial gradient.
glow = Image.new("RGBA", (W*SS, H*SS), (0,0,0,0)); gd = ImageDraw.Draw(glow)
cx, cy, R = int(180*SS), int(120*SS), int(620*SS)
for i in range(70, 0, -1):
    r = int(R*i/70); a = int(30*(1-i/70)**1.7)
    gd.ellipse([cx-r, cy-r, cx+r, cy+r], fill=(0x3B,0x5B,0xFF,a))
img = Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB")
d = ImageDraw.Draw(img, "RGBA")

def mark(size, x, y, target=None, blue=BLUE, amber=AMBER):
    """Hibiscus-Notch, geometry identical to the 120-unit viewBox."""
    dd = ImageDraw.Draw(target, "RGBA") if target is not None else d
    k = size*SS/120.0
    def p(v, off): return off + v*k
    dd.rounded_rectangle([p(14,x*SS), p(14,y*SS), p(106,x*SS), p(88,y*SS)], radius=p(30,0), fill=blue)
    dd.polygon([(p(32,x*SS),p(88,y*SS)), (p(32,x*SS),p(108,y*SS)), (p(52,x*SS),p(88,y*SS))], fill=blue)
    for dx, dy in [(96.0,17.0),(104.6,23.2),(101.3,33.3),(90.7,33.3),(87.4,23.2)]:
        dd.ellipse([p(dx-4,x*SS), p(dy-4,y*SS), p(dx+4,x*SS), p(dy+4,y*SS)], fill=amber)

# Oversized ghost mark bleeding off the right edge — balances a composition
# that is otherwise entirely left-weighted, without adding another element
# competing for attention. Kept low-alpha so the wordmark stays dominant.
ghost = Image.new("RGBA", (W*SS, H*SS), (0,0,0,0))
mark(540, 648, 118, target=ghost, blue=(0x3B,0x5B,0xFF,30), amber=(0xFF,0xB2,0x38,30))
img = Image.alpha_composite(img.convert("RGBA"), ghost).convert("RGB")
d = ImageDraw.Draw(img, "RGBA")

M = 90  # left margin
mark(96, M, 84)

# Wordmark
f_word = font("InstrumentSans-Bold.ttf", 78)
wx, wy = M*SS, 210*SS
d.text((wx, wy), "naktahu", font=f_word, fill=WHITE)
wlen = d.textlength("naktahu", font=f_word)
d.text((wx+wlen, wy), ".my", font=f_word, fill=BLUE)

# Tagline — the canonical brand line (CLAUDE.md), Malay-first by design.
d.text((M*SS, 320*SS), "Ilmu tempatan, jawapan seketika.",
       font=font("InstrumentSans-Regular.ttf", 34), fill=WHITE)
d.text((M*SS, 372*SS), "Jawapan bersumber rasmi untuk soalan kerajaan Malaysia.",
       font=font("InstrumentSans-Regular.ttf", 25), fill=MUTED)

# Agency stamp chips — same double-rule + mono treatment as a real citation.
f_chip = font("IBMPlexMono-Bold.ttf", 21)
x = M*SS; y = 468*SS
for label in ["LHDN", "KWSP", "SSM", "PERKESO", "KKM", "JPN"]:
    tw = d.textlength(label, font=f_chip)
    pad_x, pad_y = 18*SS, 11*SS
    box = [x, y, x + tw + pad_x*2, y + 21*SS + pad_y*2]
    d.rounded_rectangle(box, radius=7*SS, fill=(0x3B,0x5B,0xFF,26),
                        outline=(0x3B,0x5B,0xFF,150), width=max(1,2*SS//2))
    inset = 3*SS
    d.rounded_rectangle([box[0]+inset, box[1]+inset, box[2]-inset, box[3]-inset],
                        radius=5*SS, outline=(0x3B,0x5B,0xFF,70), width=max(1,SS//2))
    d.text((x + pad_x, y + pad_y - 2*SS), label, font=f_chip, fill=(0x8F,0xA6,0xFF))
    x = box[2] + 14*SS

d.text((M*SS, 556*SS), "Bukan nasihat rasmi kerajaan  ·  naktahu.my",
       font=font("InstrumentSans-Regular.ttf", 20), fill=(0x6C,0x72,0x80))

out = ROOT/"apps/web/public/og-image.png"
img.resize((W, H), Image.LANCZOS).save(out, optimize=True)
print(f"wrote {out} ({out.stat().st_size//1024} KB)")
