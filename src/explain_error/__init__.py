"""explain-error: plain-English explanations and fixes for error messages."""

__version__ = "0.2.0"

from .matcher import Match, Rule, explain, load_rules  # noqa: E402

__all__ = ["Match", "Rule", "explain", "load_rules", "__version__"]
