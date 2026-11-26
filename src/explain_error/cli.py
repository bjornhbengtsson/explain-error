"""Command-line entry point.

    python app.py 2>&1 | explain-error         # explain piped output
    explain-error -- python app.py              # run a command, explain if it fails
    explain-error "TypeError: x is not a function"
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter

from . import __version__
from .matcher import explain, find_location, load_rules
from .render import Style, render, use_color

EXAMPLES = """\
examples:
  python app.py 2>&1 | explain-error
  explain-error -- npm run build
  explain-error "ModuleNotFoundError: No module named 'cv2'"
  explain-error --ai -- cargo build
"""


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="explain-error",
        description="Explain error messages in plain English, with fixes. Works offline.",
        epilog=EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("error", nargs="*", help="error text (otherwise read from stdin)")
    p.add_argument("--ai", action="store_true", help="also ask Claude (needs the [ai] extra and an API key)")
    p.add_argument("--model", help="Claude model for --ai (default: claude-opus-5-5)")
    p.add_argument("--all", action="store_true", help="show every matching rule, not only the best one")
    p.add_argument("--json", action="store_true", help="print machine-readable JSON")
    p.add_argument("--list", action="store_true", help="list the built-in rules and exit")
    p.add_argument("--color", dest="color", action="store_true", default=None, help="force colored output")
    p.add_argument("--no-color", dest="color", action="store_false", help="disable colored output")
    p.add_argument("--version", action="version", version=f"explain-error {__version__}")
    return p


def _run_command(cmd: list[str]) -> tuple[str, int]:
    """Run cmd, echo its output live, and return (output, exit code)."""
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            shell=sys.platform == "win32",  # so `npm`, `.bat` and built-ins resolve on Windows
        )
    except FileNotFoundError:
        msg = f"{cmd[0]}: command not found"
        print(msg, file=sys.stderr)
        return msg, 127
    chunks = []
    with proc:
        assert proc.stdout is not None
        for line in proc.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
            chunks.append(line)
    return "".join(chunks), proc.returncode


def _list_rules(style: Style) -> None:
    rules = load_rules()
    counts = Counter(r.language for r in rules)
    for lang in sorted(counts):
        print(style.bold(f"{lang} ({counts[lang]})"))
        for r in rules:
            if r.language == lang:
                print(f"  {style.cyan(r.id):<40} {style.dim(r.title)}")
    print(style.dim(f"\n{len(rules)} rules"))


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")

    argv = sys.argv[1:] if argv is None else argv
    command: list[str] | None = None
    if "--" in argv:
        i = argv.index("--")
        argv, command = argv[:i], argv[i + 1 :]

    args = _parser().parse_args(argv)
    style = Style(use_color(force=args.color))

    if args.list:
        _list_rules(style)
        return 0

    exit_code = 0
    if command:
        text, exit_code = _run_command(command)
        if exit_code == 0:
            return 0
        print()
    elif args.error:
        text = " ".join(args.error)
    elif not sys.stdin.isatty():
        text = sys.stdin.read()
    else:
        _parser().print_help()
        return 2

    if not text.strip():
        print("explain-error: no input", file=sys.stderr)
        return 2

    matches = explain(text)

    ai_text = None
    ai_error = None
    if args.ai:
        from .ai import AIError, explain_with_ai

        if not args.json:
            print(style.dim("Asking Claude..."), file=sys.stderr)
        try:
            ai_text = explain_with_ai(
                text,
                location=find_location(text),
                hint=matches[0] if matches else None,
                model=args.model,
            )
        except AIError as e:
            ai_error = str(e)

    if args.json:
        print(
            json.dumps(
                {
                    "matches": [m.to_dict() for m in (matches if args.all else matches[:1])],
                    "ai": ai_text,
                    "ai_error": ai_error,
                    "command_exit_code": exit_code if command else None,
                },
                indent=2,
            )
        )
    else:
        if matches:
            print(render(matches, style, args.all))
        elif not args.ai:
            print(style.yellow("No built-in rule matches this error yet."))
            print("  - Try `explain-error --ai` to ask Claude about it.")
            print("  - Or add a rule: https://github.com/bjornhbengtsson/explain-error/blob/main/CONTRIBUTING.md")
        if ai_text:
            print()
            print(style.bold("Claude says:"))
            print(style.code(ai_text))
        if ai_error:
            print(style.red("AI mode failed: ") + ai_error, file=sys.stderr)

    if command:
        return exit_code
    return 0 if (matches or ai_text) else 1


if __name__ == "__main__":
    sys.exit(main())
