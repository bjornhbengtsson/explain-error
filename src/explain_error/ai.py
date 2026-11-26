"""Optional: ask Claude to explain an error that no rule (or not enough) covers.

Needs `pip install anthropic` and Anthropic credentials
(ANTHROPIC_API_KEY, or a profile from `ant auth login`).
"""

from __future__ import annotations

import os

from .matcher import Location, Match

DEFAULT_MODEL = "claude-opus-5-5"
MAX_CHARS = 200_000

# Models that accept the server-side refusal fallback parameter.
_FALLBACK_MODELS = {
    "claude-opus-5-5",
    "claude-opus-5",
    "claude-sonnet-5-5",
    "claude-fable-5-1",
    "claude-fable-5-2",
}

SYSTEM_PROMPT = """\
You explain programming errors to developers, many of them beginners.

Given an error message or log, reply in this format and nothing else:

**What happened:** one or two plain-English sentences on what the error means.
**Why:** the most likely cause in this specific case, based on the details in the log.
**Fix:** a short numbered list of concrete steps, most likely fix first. Include exact \
commands or code where they help, in fenced code blocks.

Be specific to the log you were given; don't list every possible cause of this error type. \
If the log is cut off or ambiguous, say what extra information would settle it. \
Keep the whole reply under 250 words."""


class AIError(Exception):
    pass


def _build_prompt(text: str, location: Location | None, hint: Match | None, cut: bool) -> str:
    parts = []
    if hint:
        parts.append(
            f"An offline rule matched this as: {hint.title} ({hint.rule.id}). "
            "Use that as a hint, but trust the log if it disagrees."
        )
    if location:
        parts.append(f"The error seems to come from {location}.")
    if cut:
        parts.append(f"The log was longer than {MAX_CHARS} characters; only its end is included.")
    parts.append(f"<error_log>\n{text}\n</error_log>")
    return "\n\n".join(parts)


def explain_with_ai(
    text: str,
    location: Location | None = None,
    hint: Match | None = None,
    model: str | None = None,
) -> str:
    try:
        import anthropic
    except ImportError as e:
        raise AIError(
            "AI mode needs the Anthropic SDK. Install it with:\n"
            '    pipx install --force "xerr[ai]"   (if you installed with pipx)\n'
            "    pip install anthropic             (otherwise)"
        ) from e

    model = model or os.environ.get("EXPLAIN_ERROR_MODEL") or DEFAULT_MODEL
    cut = len(text) > MAX_CHARS
    if cut:
        # The end of a log usually holds the error that stopped the program.
        text = text[-MAX_CHARS:]

    params = dict(
        model=model,
        max_tokens=16000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _build_prompt(text, location, hint, cut)}],
    )

    try:
        client = anthropic.Anthropic()
        if model in _FALLBACK_MODELS:
            response = client.beta.messages.create(
                **params,
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        else:
            response = client.messages.create(**params)
    except anthropic.AuthenticationError as e:
        raise AIError(
            "Anthropic rejected the credentials. Set ANTHROPIC_API_KEY or run `ant auth login`."
        ) from e
    except anthropic.RateLimitError as e:
        raise AIError("Rate limited by the Anthropic API. Wait a bit and try again.") from e
    except anthropic.NotFoundError as e:
        raise AIError(f"Model `{model}` was not found. Check --model / EXPLAIN_ERROR_MODEL.") from e
    except anthropic.APIStatusError as e:
        raise AIError(f"Anthropic API error ({e.status_code}): {e.message}") from e
    except anthropic.APIConnectionError as e:
        raise AIError("Couldn't reach the Anthropic API. Check your internet connection.") from e
    except anthropic.AnthropicError as e:
        # Raised before any request when no credentials can be found.
        raise AIError(
            f"{e}\nSet ANTHROPIC_API_KEY or run `ant auth login` to use --ai."
        ) from e

    if response.stop_reason == "refusal":
        raise AIError("Claude declined to explain this log.")

    reply = "".join(block.text for block in response.content if block.type == "text").strip()
    if not reply:
        raise AIError("Claude returned an empty reply.")
    return reply
