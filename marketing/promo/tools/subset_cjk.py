"""Build tiny Noto Sans SC subsets holding only the CJK glyphs the ZH cut uses.

Fontsource ships Noto Sans SC as ~100 unicode-range chunks per weight. This
collects every non-ASCII codepoint in the given text, subsets each chunk that
covers one, and merges the pieces into a single woff2 per weight, so the render
never depends on system CJK fonts.

usage: python subset_cjk.py <fontsource-pkg-dir> <text-file> <out-dir>
"""
import json
import re
import sys
from pathlib import Path

from fontTools import subset
from fontTools.merge import Merger
from fontTools.ttLib import TTFont

WEIGHTS = ["500", "700", "800"]

pkg, text_file, out_dir = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
text = text_file.read_text(encoding="utf-8")
CJK = [(0x2E80, 0x2FDF), (0x3000, 0x303F), (0x3400, 0x4DBF), (0x4E00, 0x9FFF), (0xF900, 0xFAFF), (0xFF00, 0xFFEF)]
need = sorted({ord(c) for c in text if any(a <= ord(c) <= b for a, b in CJK)})  # Han + CJK/full-width punctuation
print(f"{len(need)} codepoints needed")


def parse_ranges(spec: str):
    out = []
    for part in spec.split(","):
        part = part.strip().upper().replace("U+", "")
        if "-" in part:
            a, b = part.split("-")
            out.append((int(a, 16), int(b, 16)))
        elif "?" in part:
            out.append((int(part.replace("?", "0"), 16), int(part.replace("?", "F"), 16)))
        elif part:
            out.append((int(part, 16), int(part, 16)))
    return out


unicode_map = json.loads((pkg / "unicode.json").read_text())
chunks = {}
for key, spec in unicode_map.items():
    ranges = parse_ranges(spec)
    hit = [cp for cp in need if any(a <= cp <= b for a, b in ranges)]
    if hit:
        chunks[re.sub(r"[\[\]]", "", key)] = hit

covered = {cp for v in chunks.values() for cp in v}
missing = [chr(cp) for cp in need if cp not in covered]
if missing:
    sys.exit(f"no chunk covers: {''.join(missing)}")
print(f"{len(chunks)} chunks involved")

out_dir.mkdir(parents=True, exist_ok=True)
tmp = out_dir / "_tmp"
tmp.mkdir(exist_ok=True)
for w in WEIGHTS:
    pieces = []
    for key, cps in chunks.items():
        src = pkg / "files" / f"noto-sans-sc-{key}-{w}-normal.woff2"
        font = TTFont(src)
        opts = subset.Options()
        opts.flavor = None
        opts.layout_features = ["*"]
        opts.notdef_outline = True
        sub = subset.Subsetter(opts)
        sub.populate(unicodes=cps)
        sub.subset(font)
        p = tmp / f"{key}-{w}.otf"
        font.flavor = None
        font.save(p)
        pieces.append(str(p))
    merged = Merger().merge(pieces) if len(pieces) > 1 else TTFont(pieces[0])
    merged.flavor = "woff2"
    dst = out_dir / f"notosanssc-{w}.woff2"
    merged.save(dst)
    cmap = merged.getBestCmap()
    lost = [chr(cp) for cp in need if cp not in cmap]
    if lost:
        sys.exit(f"merge dropped glyphs for weight {w}: {''.join(lost)}")
    print(f"{dst.name}: {dst.stat().st_size // 1024} KB, {len(cmap)} mapped codepoints")
for f in tmp.iterdir():
    f.unlink()
tmp.rmdir()
