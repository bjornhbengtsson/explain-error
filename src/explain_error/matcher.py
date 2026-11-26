"""Load error rules from TOML files and match them against error text."""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from functools import lru_cache
from importlib.resources import files
from pathlib import Path

# Python import names that differ from their pip package names.
PIP_NAMES = {
    "cv2": "opencv-python",
    "PIL": "pillow",
    "sklearn": "scikit-learn",
    "yaml": "pyyaml",
    "bs4": "beautifulsoup4",
    "dotenv": "python-dotenv",
    "dateutil": "python-dateutil",
    "Crypto": "pycryptodome",
    "jwt": "pyjwt",
    "serial": "pyserial",
    "usb": "pyusb",
    "magic": "python-magic",
    "docx": "python-docx",
    "pptx": "python-pptx",
    "fitz": "pymupdf",
    "skimage": "scikit-image",
    "google.protobuf": "protobuf",
    "attr": "attrs",
    "win32api": "pywin32",
    "win32com": "pywin32",
    "gi": "PyGObject",
    "OpenGL": "PyOpenGL",
    "telegram": "python-telegram-bot",
    "discord": "discord.py",
}

_PLACEHOLDER = re.compile(r"\{(\w+)(?:\|(\w+))?\}")


def _filter(value: str, name: str | None) -> str:
    if name is None:
        return value
    if name == "root":
        return value.split(".")[0]
    if name == "pip":
        if value in PIP_NAMES:
            return PIP_NAMES[value]
        root = value.split(".")[0]
        return PIP_NAMES.get(root, root)
    return value


def fill(template: str, groups: dict[str, str | None]) -> str:
    """Replace {group} and {group|filter} with captured values.

    Braces that don't name a captured group are left alone, so rule text can
    contain code like `{}` without escaping.
    """

    def sub(m: re.Match[str]) -> str:
        key, filt = m.group(1), m.group(2)
        if key not in groups:
            return m.group(0)
        value = groups[key]
        if value is None:
            return f"<{key}>"
        return _filter(value.strip(), filt)

    return _PLACEHOLDER.sub(sub, template)


@dataclass(frozen=True)
class Rule:
    id: str
    language: str
    pattern: re.Pattern[str]
    title: str
    explain: str
    fixes: tuple[str, ...]
    examples: tuple[str, ...]
    priority: int = 50
    docs: str | None = None
    source: str = ""


@dataclass
class Location:
    file: str
    line: int | None = None
    column: int | None = None

    def __str__(self) -> str:
        out = self.file
        if self.line is not None:
            out += f":{self.line}"
            if self.column is not None:
                out += f":{self.column}"
        return out


@dataclass
class Match:
    rule: Rule
    title: str
    explain: str
    fixes: list[str]
    matched_text: str
    position: int
    location: Location | None = None
    groups: dict[str, str | None] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.rule.id,
            "language": self.rule.language,
            "title": self.title,
            "explanation": self.explain,
            "fixes": self.fixes,
            "matched": self.matched_text,
            "location": (
                {
                    "file": self.location.file,
                    "line": self.location.line,
                    "column": self.location.column,
                }
                if self.location
                else None
            ),
            "docs": self.rule.docs,
        }


def _parse_rules(text: str, source: str) -> list[Rule]:
    data = tomllib.loads(text)
    rules = []
    for raw in data.get("rule", []):
        try:
            rules.append(
                Rule(
                    id=raw["id"],
                    language=raw.get("language", Path(source).stem),
                    pattern=re.compile(raw["pattern"], re.MULTILINE),
                    title=raw["title"],
                    explain=raw["explain"].strip(),
                    fixes=tuple(raw.get("fixes", [])),
                    examples=tuple(raw.get("examples", [])),
                    priority=int(raw.get("priority", 50)),
                    docs=raw.get("docs"),
                    source=source,
                )
            )
        except (KeyError, re.error) as e:
            raise ValueError(f"Bad rule in {source}: {raw.get('id', '?')}: {e}") from e
    return rules


@lru_cache(maxsize=1)
def load_rules() -> tuple[Rule, ...]:
    rules: list[Rule] = []
    rules_dir = files("explain_error") / "rules"
    for entry in sorted(rules_dir.iterdir(), key=lambda p: p.name):
        if entry.name.endswith(".toml"):
            rules.extend(_parse_rules(entry.read_text(encoding="utf-8"), entry.name))
    return tuple(rules)


# Patterns that point at where an error happened, tried in order.
# Python tracebacks list the innermost frame last; most others list it first.
_LOCATION_PATTERNS: list[tuple[re.Pattern[str], bool]] = [
    # Python: File "app.py", line 12, in main
    (re.compile(r'File "(?P<file>[^"<>]+)", line (?P<line>\d+)'), True),
    # Rust: --> src/main.rs:4:9
    (re.compile(r"-->\s+(?P<file>[^\s:]+):(?P<line>\d+):(?P<col>\d+)"), False),
    # TypeScript: src/app.ts(3,7): error TS2322
    (re.compile(r"^(?P<file>[^\s()]+\.[cm]?tsx?)\((?P<line>\d+),(?P<col>\d+)\)", re.M), False),
    # gcc/clang/tsc --pretty/go: file.c:10:5: error
    (re.compile(r"^(?P<file>[^\s:]+\.\w+):(?P<line>\d+):(?:(?P<col>\d+):)?\s", re.M), False),
    # Node/JS stack: at fn (/path/app.js:10:15)  or  at /path/app.js:10:15
    (re.compile(r"at (?:.*?\()?(?P<file>(?:[A-Za-z]:)?[^\s():]+\.[cm]?[jt]sx?):(?P<line>\d+):(?P<col>\d+)"), False),
    # Java stack: at com.x.Main.run(Main.java:12)
    (re.compile(r"at [\w$.<>]+\((?P<file>[\w$]+\.(?:java|kt|scala)):(?P<line>\d+)\)"), False),
    # Go panic: /home/me/app/main.go:12 +0x1d
    (re.compile(r"^\s+(?P<file>\S+\.go):(?P<line>\d+)", re.M), False),
]

_LIBRARY_HINTS = ("site-packages", "node_modules", "/lib/python", "\\lib\\python", "node:internal", "<frozen")


def find_location(text: str) -> Location | None:
    for pattern, innermost_last in _LOCATION_PATTERNS:
        hits = list(pattern.finditer(text))
        if not hits:
            continue
        # Prefer the user's own code over library frames.
        own = [h for h in hits if not any(s in h.group("file") for s in _LIBRARY_HINTS)]
        pool = own or hits
        hit = pool[-1] if innermost_last else pool[0]
        col = hit.groupdict().get("col")
        return Location(hit.group("file"), int(hit.group("line")), int(col) if col else None)
    return None


def explain(text: str, rules: tuple[Rule, ...] | None = None) -> list[Match]:
    """Return every rule that matches, best first."""
    rules = load_rules() if rules is None else rules
    location = find_location(text)
    found: list[Match] = []
    for rule in rules:
        m = rule.pattern.search(text)
        if not m:
            continue
        groups = m.groupdict()
        found.append(
            Match(
                rule=rule,
                title=fill(rule.title, groups),
                explain=fill(rule.explain, groups),
                fixes=[fill(f, groups) for f in rule.fixes],
                matched_text=m.group(0).strip(),
                position=m.start(),
                location=location,
                groups=groups,
            )
        )
    # Higher priority wins; on a tie, the later match wins, since the last
    # error in a log is usually the one that stopped the program.
    found.sort(key=lambda x: (-x.rule.priority, -x.position))
    return found
