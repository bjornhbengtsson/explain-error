import io
import shutil
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from explain_error.cli import main  # noqa: E402
from explain_error.shell import NAME_PLACEHOLDER, SHELLS, script_for  # noqa: E402


class _BytesStdout(io.StringIO):
    """StringIO with a .buffer, like the real sys.stdout."""

    def __init__(self):
        super().__init__()
        self.buffer = io.BytesIO()


class ShellScriptTests(unittest.TestCase):
    def test_every_shell_has_a_script_with_the_name_filled_in(self):
        for shell in SHELLS:
            with self.subTest(shell=shell):
                script = script_for(shell, "wtf")
                self.assertNotIn(NAME_PLACEHOLDER, script)
                self.assertIn("wtf", script)
                self.assertNotIn("\r", script)
                self.assertTrue(script.isascii(), "keep hooks ASCII so every console decodes them")

    def test_rejects_bad_names_and_shells(self):
        with self.assertRaises(ValueError):
            script_for("bash", "rm -rf")
        with self.assertRaises(ValueError):
            script_for("tcsh")

    def test_pwsh_alias(self):
        self.assertEqual(script_for("pwsh"), script_for("powershell"))

    def test_init_prints_script_bytes(self):
        out = _BytesStdout()
        with redirect_stdout(out):
            code = main(["init", "bash"])
        self.assertEqual(code, 0)
        text = out.buffer.getvalue().decode()
        self.assertIn("__xerr_prompt_hook", text)
        self.assertNotIn("\r\n", text)

    def test_init_without_shell_prints_setup(self):
        out = _BytesStdout()
        with redirect_stdout(out):
            code = main(["init"])
        self.assertEqual(code, 0)
        self.assertIn("~/.zshrc", out.getvalue())

    def _check_syntax(self, shell: str, *args: str) -> None:
        exe = _real_shell(shell)
        if not exe:
            self.skipTest(f"{shell} not installed")
        # Send bytes, so Windows can't turn the script's LF line endings into CRLF.
        result = subprocess.run([exe, *args], input=script_for(shell).encode(), capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))

    def test_bash_script_parses(self):
        self._check_syntax("bash", "-n")

    def test_zsh_script_parses(self):
        self._check_syntax("zsh", "-n")

    def test_fish_script_parses(self):
        self._check_syntax("fish", "--no-execute")


def _real_shell(name: str) -> str | None:
    path = shutil.which(name)
    # On Windows, System32\bash.exe is the WSL launcher, which fails when no
    # Linux distribution is installed. Only use a real bash (e.g. Git Bash).
    if path and "system32" in path.lower():
        return None
    return path


if __name__ == "__main__":
    unittest.main()
