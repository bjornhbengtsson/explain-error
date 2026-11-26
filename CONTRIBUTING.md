# Contributing

The most useful contribution is a new rule for an error you've actually hit. No Python knowledge is needed: rules are plain TOML.

## Add a rule

1. Pick the file for the ecosystem in `src/explain_error/rules/` (or create one, e.g. `php.toml`).
2. Add a `[[rule]]` block:

```toml
[[rule]]
id = "lang-short-name"              # unique, kebab-case, prefixed by language
language = "python"
priority = 50                       # optional; higher wins when several rules match
pattern = '''regex with (?P<name>named groups)'''
title = "One line, using {name}"
explain = '''
Two or three sentences: what the error means and its most common causes.
'''
fixes = [
  "Most likely fix first, with the exact command in `backticks`",
  "Second most likely fix",
]
docs = "https://..."                # optional
examples = ['''A real error message this rule must match''']
```

3. Run the tests: `python -m unittest discover -s tests` (or `pytest`). They check that every rule matches its own examples, and that its ids and placeholders are valid.
4. Try it: `PYTHONPATH=src python -m explain_error "your error text"`

## Writing good rules

- **Match the stable part of the message.** Leave out paths, line numbers and versions; put names you want to quote in named groups.
- **Use `'''triple single quotes'''` for patterns and examples**, so backslashes and quotes don't need escaping. A string may end with up to two extra quotes: `'''No module named 'x''''`.
- **Placeholders:** `{name}` inserts a captured group. `{module|pip}` maps an import name to its pip package, and `{module|root}` keeps the part before the first dot. Braces that don't name a group are left alone, so code like `{user.name}` is fine.
- **Explain for a beginner.** Use plain words, give the most common cause first, and skip the history lesson.
- **Make fixes concrete.** Write a command someone can paste, not "check your configuration."
- **Set priority** above 50 for very specific rules, so they beat generic ones like `py-attr` or `sh-permission-denied`.
- **Use real examples.** Paste the error exactly as the tool prints it; include two if the wording varies between versions.

## Development

```bash
python -m venv .venv
.venv/bin/pip install -e ".[dev,ai]"    # Windows: .venv\Scripts\pip install -e ".[dev,ai]"
pytest
```
