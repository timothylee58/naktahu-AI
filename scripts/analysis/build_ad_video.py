"""Assemble the NakTahu 9:16 ad reel from generated key-frames + text overlays.

Silent by design: burn-in kinetic typography per the storyboard beats; VO + BGM
are added in the final edit (licensed audio can't be generated here).
"""
from __future__ import annotations

import os
import subprocess

ASSETS = "/opt/cursor/artifacts/assets"
OUT = "/opt/cursor/artifacts"
WORK = "/tmp/adbuild"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
os.makedirs(WORK, exist_ok=True)
FPS = 30

# segment = (image, duration_seconds, [ (text, fontsize, y, start_offset, is_feature) ])
SEGMENTS = [
    ("ad_01_hook.png", 7, [
        ("Penat scroll", 92, 170, 0.2, False),
        ("cari jawapan legit?", 92, 290, 0.5, False),
        ("Tired of scrolling for real answers?", 44, 1660, 1.2, False),
    ]),
    ("ad_02_product.png", 14, [
        ("Terlalu banyak noise.", 80, 170, 0.3, False),
        ("Tak cukup kejelasan.", 80, 285, 0.7, False),
        ("Too much noise. Not enough clarity.", 44, 1660, 1.4, False),
    ]),
    ("ad_03_features.png", 14, [
        ("NakTahu.my", 84, 140, 0.2, False),
        ("Search Smart", 62, 640, 1.0, True),
        ("Verified & Localized  \u00b7 MY", 62, 780, 2.2, True),
        ("Zero Fluff", 62, 920, 3.4, True),
        ("Verified, curated Malaysian gov info.", 42, 1660, 5.0, False),
    ]),
    ("ad_04_cta.png", 7, [
        ("NakTahu.my", 100, 800, 0.3, False),
        ("Tap the link below to explore now", 46, 980, 1.0, False),
        ("Stop guessing. Start knowing.", 44, 1660, 1.8, False),
    ]),
]


def esc(path: str) -> str:
    return path.replace("\\", "\\\\").replace(":", "\\:")


def build_segment(idx: int, image: str, dur: int, texts) -> str:
    seg_out = f"{WORK}/seg_{idx}.mp4"
    # base: scale to height 1920, centre-crop to 1080 wide, gentle zoom
    filters = [
        "scale=-1:1920",
        "crop=1080:1920",
        "setsar=1",
    ]
    for i, (text, size, y, start, is_feature) in enumerate(texts):
        tf = f"{WORK}/s{idx}_t{i}.txt"
        with open(tf, "w", encoding="utf-8") as fh:
            fh.write(text)
        a = (f"if(lt(t,{start}),0,"
             f"if(lt(t,{start}+0.4),(t-{start})/0.4,"
             f"if(lt(t,{dur}-0.4),1,max(0,({dur}-t)/0.4))))")
        box = ":box=1:boxcolor=#1d4ed8@0.85:boxborderw=18" if is_feature else ""
        filters.append(
            f"drawtext=fontfile={esc(FONT)}:textfile={esc(tf)}:fontcolor=white:"
            f"fontsize={size}:borderw=3:bordercolor=black@0.9{box}:"
            f"x=(w-text_w)/2:y={y}:alpha='{a}'"
        )
    filters.append("format=yuv420p")
    vf = ",".join(filters)
    cmd = [
        "ffmpeg", "-y", "-loop", "1", "-framerate", str(FPS),
        "-t", str(dur), "-i", f"{ASSETS}/{image}",
        "-vf", vf, "-r", str(FPS), "-pix_fmt", "yuv420p",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", seg_out,
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return seg_out


def main() -> None:
    segs = [build_segment(i, *s) for i, s in enumerate(SEGMENTS)]
    concat_list = f"{WORK}/list.txt"
    with open(concat_list, "w") as fh:
        for s in segs:
            fh.write(f"file '{s}'\n")
    out = f"{OUT}/naktahu_ad_reel_9x16.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list,
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
         "-movflags", "+faststart", out],
        check=True, capture_output=True,
    )
    # export the four beats as IG-story stills too (first frame of each segment overlay @ ~mid)
    print("built:", out)
    dur = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", out], capture_output=True, text=True).stdout.strip()
    print("duration_s:", dur)


if __name__ == "__main__":
    main()
