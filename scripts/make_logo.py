"""Regenerate logo_sidebar.png from logo.png.

Run after replacing the brand asset:
    .venv/Scripts/python.exe scripts/make_logo.py

Why this exists: logo.png is 1550px wide but displays at ~220px. Letting the
browser do that 7x downscale uses a fast, low-quality scaler that destroys fine
strokes (the M in OSRAM rounded into blobs). Resampling once with LANCZOS, at
2x the CSS width for HiDPI, keeps it sharp.
"""
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
DISPLAY_W = 300          # must match the width= passed to st.image in app.py
SCALE = 2                # render at 2x for HiDPI displays


def main() -> None:
    src = Image.open(ROOT / "logo.png").convert("RGBA")
    w, h = src.size
    target_w = DISPLAY_W * SCALE
    target = (target_w, max(1, round(h * target_w / w)))
    out = src.resize(target, Image.LANCZOS)
    dest = ROOT / "logo_sidebar.png"
    out.save(dest)
    print(f"{src.size} -> {out.size}  ({dest.name}, displayed at {DISPLAY_W}px)")


if __name__ == "__main__":
    main()
