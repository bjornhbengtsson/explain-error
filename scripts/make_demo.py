"""Render docs/demo.gif: a scripted terminal session showing `huh` in action.

The explain-error output in the GIF is real: this script runs the CLI on the
error and draws exactly what it prints. Re-run it whenever the output changes:

    pip install pillow
    python scripts/make_demo.py            # writes docs/demo.gif
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]

COLS, ROWS = 92, 30
FONT_SIZE = 17
PAD = 22
TITLE_H = 34

BG = (13, 17, 23)
TITLE_BG = (22, 27, 34)
FG = (230, 237, 243)
DIM = (125, 133, 144)
COLORS = {
    "31": (255, 123, 114),  # red
    "32": (126, 231, 135),  # green
    "33": (227, 179, 65),   # yellow
    "34": (121, 192, 255),  # blue
    "36": (121, 192, 255),  # cyan
}

PROMPT_DIR = "~/vision"
TRACEBACK = """\
Traceback (most recent call last):
  File "/home/me/vision/main.py", line 3, in <module>
    import cv2
ModuleNotFoundError: No module named 'cv2'"""


@dataclass
class Style:
    fg: tuple[int, int, int] = FG
    bold: bool = False


@dataclass
class Terminal:
    lines: list[list[tuple[str, Style]]] = field(default_factory=lambda: [[]])

    def write(self, text: str, style: Style | None = None) -> None:
        style = style or Style()
        parts = text.split("\n")
        for i, part in enumerate(parts):
            if i:
                self.lines.append([])
            if part:
                self.lines[-1].append((part, style))

    def write_ansi(self, text: str) -> None:
        style = Style()
        for token in re.split(r"(\033\[[0-9;]*m)", text):
            m = re.fullmatch(r"\033\[([0-9;]*)m", token)
            if not m:
                self.write(token, style)
                continue
            codes = m.group(1).split(";")
            for code in codes:
                if code in ("", "0"):
                    style = Style()
                elif code == "1":
                    style = Style(style.fg, True)
                elif code == "2":
                    style = Style(DIM, style.bold)
                elif code in COLORS:
                    style = Style(COLORS[code], style.bold)


def find_font(bold: bool) -> str:
    names = (
        ["consolab.ttf", "DejaVuSansMono-Bold.ttf", "Menlo.ttc"]
        if bold
        else ["consola.ttf", "DejaVuSansMono.ttf", "Menlo.ttc"]
    )
    for name in names:
        try:
            ImageFont.truetype(name, FONT_SIZE)
            return name
        except OSError:
            continue
    raise SystemExit("No monospace font found; install DejaVu Sans Mono or pass --font.")


class Renderer:
    def __init__(self, regular: str, bold: str):
        self.font = ImageFont.truetype(regular, FONT_SIZE)
        self.bold = ImageFont.truetype(bold, FONT_SIZE)
        self.cw = round(self.font.getlength("M"))
        self.ch = round(FONT_SIZE * 1.4)
        self.w = PAD * 2 + COLS * self.cw
        self.h = TITLE_H + PAD * 2 + ROWS * self.ch

    def frame(self, term: Terminal, cursor: bool) -> Image.Image:
        img = Image.new("RGB", (self.w, self.h), BG)
        d = ImageDraw.Draw(img)
        d.rectangle([0, 0, self.w, TITLE_H], fill=TITLE_BG)
        for i, color in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
            x = 18 + i * 20
            d.ellipse([x, 11, x + 12, 23], fill=color)
        title = "explain-error"
        d.text(((self.w - self.font.getlength(title)) / 2, 8), title, font=self.font, fill=DIM)

        visible = term.lines[-ROWS:]
        for row, segments in enumerate(visible):
            x = PAD
            y = TITLE_H + PAD + row * self.ch
            for text, style in segments:
                font = self.bold if style.bold else self.font
                d.text((x, y), text, font=font, fill=style.fg)
                x += len(text) * self.cw
            if cursor and row == len(visible) - 1:
                d.rectangle([x, y + 2, x + self.cw - 2, y + self.ch - 4], fill=FG)
        return img


class Movie:
    def __init__(self, renderer: Renderer):
        self.r = renderer
        self.term = Terminal()
        self.frames: list[Image.Image] = []
        self.durations: list[int] = []

    def snap(self, ms: int, cursor: bool = True) -> None:
        self.frames.append(self.r.frame(self.term, cursor))
        self.durations.append(ms)

    def prompt(self) -> None:
        self.term.write(PROMPT_DIR, Style(COLORS["34"], True))
        self.term.write(" $ ", Style(DIM))

    def type(self, text: str, pause_after: int = 350) -> None:
        for i, ch in enumerate(text):
            self.term.write(ch, Style(FG, True))
            self.snap(55 if i < len(text) - 1 else pause_after)

    def enter(self) -> None:
        self.term.write("\n")

    def out(self, text: str, ms: int = 0, style: Style | None = None) -> None:
        self.term.write(text, style)
        if ms:
            self.snap(ms, cursor=False)

    def out_lines_ansi(self, text: str, ms_per_line: int) -> None:
        for line in text.rstrip("\n").split("\n"):
            self.term.write_ansi(line + "\n")
            self.snap(ms_per_line, cursor=False)


def real_explanation() -> str:
    env = {**os.environ, "FORCE_COLOR": "1", "PYTHONPATH": str(ROOT / "src")}
    env.pop("NO_COLOR", None)
    result = subprocess.run(
        [sys.executable, "-m", "explain_error", "--color"],
        input=TRACEBACK,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(f"explain-error failed:\n{result.stdout}{result.stderr}")
    # Drop lines that are noise in a short demo: the docs link and rule id.
    keep = [ln for ln in result.stdout.splitlines() if "docs:" not in ln and "rule:" not in ln]
    while keep and not keep[-1].strip():
        keep.pop()
    return "\n".join(keep)


def build(out: Path, regular: str, bold: str) -> None:
    m = Movie(Renderer(regular, bold))
    hint = Style(DIM)

    m.prompt()
    m.snap(900)
    m.type("python main.py")
    m.enter()
    m.out(TRACEBACK + "\n", 400)
    m.out("exit 1 - type huh to explain\n", 1300, hint)

    m.prompt()
    m.snap(500)
    m.type("huh", 450)
    m.enter()
    m.out("Re-run `python main.py` to capture its error? [Y/n] ")
    m.snap(700)
    m.type("y", 300)
    m.enter()
    m.out(TRACEBACK + "\n\n", 300)
    m.out_lines_ansi(real_explanation(), 70)
    m.out("\n")
    m.snap(4200, cursor=False)

    m.prompt()
    m.snap(500)
    m.type("pip install opencv-python")
    m.enter()
    m.out("Collecting opencv-python\n", 500)
    m.out("Successfully installed numpy-2.1.3 opencv-python-4.10.0.84\n", 600)
    m.prompt()
    m.snap(400)
    m.type("python main.py")
    m.enter()
    m.out("camera ready: 1280x720\n", 300, Style(COLORS["32"]))
    m.prompt()
    m.snap(3500)

    # One shared palette keeps colors stable between frames and the file small.
    sample = Image.new("RGB", (m.r.w, m.r.h * 3))
    for i, idx in enumerate([len(m.frames) // 3, (len(m.frames) * 2) // 3, -1]):
        sample.paste(m.frames[idx], (0, i * m.r.h))
    palette = sample.quantize(colors=128, method=Image.Quantize.MEDIANCUT)
    frames = [f.quantize(palette=palette, dither=Image.Dither.NONE) for f in m.frames]

    out.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        out,
        save_all=True,
        append_images=frames[1:],
        duration=m.durations,
        loop=0,
        optimize=True,
        disposal=1,
    )
    total = sum(m.durations) / 1000
    print(f"wrote {out} ({len(frames)} frames, {total:.1f}s, {out.stat().st_size // 1024} KB)")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", type=Path, default=ROOT / "docs" / "demo.gif")
    p.add_argument("--font", help="regular monospace font file")
    p.add_argument("--bold-font", help="bold monospace font file")
    args = p.parse_args()
    build(args.out, args.font or find_font(False), args.bold_font or args.font or find_font(True))


if __name__ == "__main__":
    main()
