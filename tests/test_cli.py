import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from explain_error.cli import main  # noqa: E402


def run(argv, stdin=None):
    out = io.StringIO()
    fake_stdin = io.StringIO(stdin or "")
    fake_stdin.isatty = lambda: stdin is None  # type: ignore[method-assign]
    with redirect_stdout(out), mock.patch.object(sys, "stdin", fake_stdin):
        code = main(argv)
    return code, out.getvalue()


class CliTests(unittest.TestCase):
    def test_argument_input(self):
        code, out = run(["--no-color", "ReferenceError: foo is not defined"])
        self.assertEqual(code, 0)
        self.assertIn("`foo` doesn't exist here", out)
        self.assertIn("rule: js-not-defined", out)

    def test_stdin_input(self):
        code, out = run(["--no-color"], stdin="fatal: not a git repository (or any of the parent directories): .git\n")
        self.assertEqual(code, 0)
        self.assertIn("isn't a git repository", out)

    def test_json_output(self):
        code, out = run(["--json", "IndexError: list index out of range"])
        data = json.loads(out)
        self.assertEqual(code, 0)
        self.assertEqual(data["matches"][0]["id"], "py-index-error")

    def test_unknown_error_exits_1(self):
        code, out = run(["--no-color", "the flux capacitor is unhappy"])
        self.assertEqual(code, 1)
        self.assertIn("No built-in rule matches", out)

    def test_run_mode_passes_through_success(self):
        code, out = run(["--no-color", "--", sys.executable, "-c", "print('hello')"])
        self.assertEqual(code, 0)
        self.assertIn("hello", out)
        self.assertNotIn("error:", out)

    def test_run_mode_explains_failure_and_keeps_exit_code(self):
        code, out = run(["--no-color", "--", sys.executable, "-c", "import definitely_not_a_module_xyz"])
        self.assertEqual(code, 1)
        self.assertIn("Traceback", out)  # the program's own output is shown
        self.assertIn("py-module-not-found", out)

    def test_list(self):
        code, out = run(["--no-color", "--list"])
        self.assertEqual(code, 0)
        self.assertIn("py-module-not-found", out)


if __name__ == "__main__":
    unittest.main()
