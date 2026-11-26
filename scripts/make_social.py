"""Render docs/social-preview.png, the 1280x640 card shown when the repo link is shared.

    pip install pillow
    python scripts/make_social.py

Then upload it in the repo's Settings > General > Social preview.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
W, H = 1280, 640

BG = (13, 17, 23)
CARD = (22, 27, 34)
BORDER = (48, 54, 61)
FG = (230, 237, 243)
MUTED = (139, 148, 158)
DIM = (110, 118, 129)
RED = (255, 123, 114)
GREEN = (126, 231, 135)
BLUE = (121, 192, 255)
YELLOW = (227, 179, 65)

SANS_BOLD = ["segoeuib.ttf", "DejaVuSans-Bold.ttf", "Arial Bold.ttf", "Helvetica.ttc"]
SANS = ["segoeui.ttf", "DejaVuSans.ttf", "Arial.ttf", "Helvetica.ttc"]
MONO = ["consola.ttf", "DejaVuSansMono.ttf", "Menlo.ttc"]
MONO_BOLD = ["consolab.ttf", "DejaVuSansMono-Bold.ttf", "Menlo.ttc"]


def font(candidates: list[str], size: int) -> ImageFont.FreeTypeFont:
    for name in candidates:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    raise SystemExit(f"None of these fonts were found: {candidates}")


def pill(d: ImageDraw.ImageDraw, x: int, y: int, text: str, f: ImageFont.FreeTypeFont) -> int:
    w = int(f.getlength(text)) + 28
    d.rounded_rectangle([x, y, x + w, y + 40], radius=20, fill=CARD, outline=BORDER, width=2)
    d.text((x + 14, y + 20), text, font=f, fill=FG, anchor="lm")
    return x + w + 12


def build(out: Path) -> None:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    # Left: name, promise, facts, install.
    x = 80
    d.text((x, 118), "explain-error", font=font(SANS_BOLD, 76), fill=FG)
    tagline = font(SANS, 34)
    d.text((x, 222), "Your error, in plain English.", font=tagline, fill=MUTED)
    d.text((x, 266), "With the fix.", font=tagline, fill=MUTED)

    small = font(SANS, 21)
    px = x
    for label in ("105 rules", "9 ecosystems", "offline"):
        px = pill(d, px, 352, label, small)
    px = x
    for label in ("shell mode", "agent skill"):
        px = pill(d, px, 404, label, small)

    mono = font(MONO, 26)
    mono_b = font(MONO_BOLD, 26)
    box_w = 46 + int(mono_b.getlength("pipx install xerr")) + 22
    d.rounded_rectangle([x, 488, x + box_w, 540], radius=10, fill=CARD, outline=BORDER, width=2)
    d.text((x + 20, 514), "$", font=mono, fill=DIM, anchor="lm")
    d.text((x + 46, 514), "pipx install xerr", font=mono_b, fill=GREEN, anchor="lm")

    # Right: a terminal card telling the whole story in five lines.
    cx0, cy0, cx1, cy1 = 650, 118, 1200, 540
    d.rounded_rectangle([cx0, cy0, cx1, cy1], radius=16, fill=CARD, outline=BORDER, width=2)
    for i, color in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        dx = cx0 + 24 + i * 22
        d.ellipse([dx, cy0 + 20, dx + 13, cy0 + 33], fill=color)
    d.line([cx0, cy0 + 52, cx1, cy0 + 52], fill=BORDER, width=2)

    t = font(MONO, 21)
    tb = font(MONO_BOLD, 21)
    lines = [
        [("$ ", DIM, t), ("python main.py", FG, tb)],
        [("ModuleNotFoundError:", RED, t)],
        [("  No module named 'cv2'", FG, t)],
        [("exit 1 - type huh to explain", DIM, t)],
        [],
        [("$ ", DIM, t), ("huh", FG, tb)],
        [("error: ", RED, tb), ("Python can't find", FG, tb)],
        [("       the module ", FG, tb), ("cv2", BLUE, tb)],
        [],
        [("  Try: ", GREEN, t), ("python -m pip install", BLUE, t)],
        [("       opencv-python", BLUE, t)],
    ]
    ly = cy0 + 76
    for segments in lines:
        lx = cx0 + 28
        for text, color, f in segments:
            d.text((lx, ly), text, font=f, fill=color)
            lx += f.getlength(text)
        ly += 31

    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, optimize=True)
    print(f"wrote {out} ({out.stat().st_size // 1024} KB)")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", type=Path, default=ROOT / "docs" / "social-preview.png")
    build(p.parse_args().out)


if __name__ == "__main__":
    main()
