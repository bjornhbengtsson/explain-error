---
name: explain-error
description: Explain a failing command, stack trace or compiler error in plain English with concrete fixes, using the explain-error rule database (100+ curated rules for Python, JavaScript/Node, TypeScript, React, git, Rust, Go, Java, C/C++, shell and Docker). Use when a command, build or test fails, when the user pastes an error or traceback, or when the user asks what an error means or how to fix it.
---

# explain-error

Turn an error into a short explanation the user can follow: what happened, why, and how to fix it.

## 1. Get a structured diagnosis

Prefer the `explain-error` CLI, because its rules are reviewed and its fixes are specific (for example, it knows that `import cv2` needs `pip install opencv-python`).

Re-run the failing command through it:

```bash
explain-error --json -- <the failing command>
```

Or pass error text you already have:

```bash
explain-error --json "<the error line>"
```

If `explain-error` isn't installed, run it without installing: `uvx xerr --json ...`. If that fails too, skip to step 2 and reason from the log alone.

The JSON has `matches[0]` with `title`, `explanation`, `fixes`, `location` (file and line, when found) and `id`. An empty `matches` list means no rule covers this error.

## 2. Check it against the real context

A rule describes the usual cause. Before answering, read the code at `location` (or the last frame of the user's own code in the trace) and confirm which cause applies here. If the code shows a different cause, trust the code.

## 3. Answer the user

Keep it short and in this order:

- **What happened:** one plain-English sentence.
- **Why here:** the specific cause in *their* code, citing the file and line.
- **Fix:** the one fix that applies, as a command or a code change. Mention a second option only if the first might not apply.

If you're fixing the code yourself rather than explaining, apply the fix, re-run the command, and say in one line what the error was.

Don't paste the whole rule output back to the user, and don't list every possible cause.
