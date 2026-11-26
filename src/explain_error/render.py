"""Terminal output."""

from __future__ import annotations

import os
import re
import sys
import textwrap

from .matcher import Match


def _enable_windows_ansi() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(handle, mode.value | 0x0004)  # VT processing
    except Exception:
        pass


def use_color(stream=sys.stdout, force: bool | None = None) -> bool:
    if force is not None:
        return force
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    return hasattr(stream, "isatty") and stream.isatty()


class Style:
    def __init__(self, enabled: bool):
        self.enabled = enabled
        if enabled:
            _enable_windows_ansi()

    def _wrap(self, code: str, s: str) -> str:
        return f"\033[{code}m{s}\033[0m" if self.enabled else s

    def bold(self, s: str) -> str:
        return self._wrap("1", s)

    def dim(self, s: str) -> str:
        return self._wrap("2", s)

    def red(self, s: str) -> str:
        return self._wrap("1;31", s)

    def green(self, s: str) -> str:
        return self._wrap("32", s)

    def cyan(self, s: str) -> str:
        return self._wrap("36", s)

    def yellow(self, s: str) -> str:
        return self._wrap("33", s)

    def code(self, s: str) -> str:
        """Highlight `inline code` spans."""
        if not self.enabled:
            return s
        return re.sub(r"`([^`]+)`", lambda m: self.cyan(m.group(1)), s)


def _width() -> int:
    try:
        return max(40, min(100, os.get_terminal_size().columns) - 2)
    except OSError:
        return 88


def _wrap(text: str, indent: str) -> str:
    width = _width()
    paragraphs = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
    return "\n\n".join(
        textwrap.fill(" ".join(p.split()), width=width, initial_indent=indent, subsequent_indent=indent)
        for p in paragraphs
    )


def render_match(m: Match, style: Style, index: int | None = None) -> str:
    lines = []
    label = "error" if index is None else f"also possible ({index})"
    lines.append(f"{style.red(label + ':')} {style.bold(style.code(m.title))}")
    lines.append(style.dim(f"  matched: {m.matched_text[:160]}"))
    if m.location:
        lines.append(f"  {style.yellow('where:')}  {m.location}")
    lines.append("")
    lines.append(style.code(_wrap(m.explain, "  ")))
    if m.fixes:
        lines.append("")
        lines.append(f"  {style.green('Try:')}")
        width = _width()
        for fix in m.fixes:
            wrapped = textwrap.fill(fix, width=width, initial_indent="    - ", subsequent_indent="      ")
            lines.append(style.code(wrapped))
    if m.rule.docs:
        lines.append("")
        lines.append(style.dim(f"  docs: {m.rule.docs}"))
    lines.append(style.dim(f"  rule: {m.rule.id}"))
    return "\n".join(lines)


def render(matches: list[Match], style: Style, show_all: bool) -> str:
    if not matches:
        return ""
    out = [render_match(matches[0], style)]
    if show_all:
        for i, m in enumerate(matches[1:], start=1):
            out.append(render_match(m, style, index=i))
    elif len(matches) > 1:
        others = ", ".join(m.rule.id for m in matches[1:4])
        out.append(style.dim(f"  ({len(matches) - 1} other rule(s) also matched: {others}. Use --all to see them.)"))
    return "\n\n".join(out)
