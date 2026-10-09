"""The documented worked examples must keep producing their documented output."""

from __future__ import annotations

import contextlib
import io
import re
import shlex
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tracecanary.cli import EXIT_REGRESSION, main

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "collector-regression"


def _fenced_block(text: str, heading: str, language: str) -> str:
    """Return the first ```language block after a Markdown heading."""
    section = text.split(heading, 1)[1]
    match = re.search(rf"```{language}\n(.*?)```", section, re.DOTALL)
    if match is None:
        raise AssertionError(f"no {language} block under {heading}")
    return match.group(1)


class CollectorRegressionExampleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.readme = (EXAMPLE / "README.md").read_text(encoding="utf-8")

    def _documented_arguments(self) -> list[str]:
        commands = [line for line in _fenced_block(self.readme, "## Run", "powershell").splitlines()
                    if line.startswith("python -m tracecanary ")]
        self.assertEqual(len(commands), 1)
        return shlex.split(commands[0])[3:]

    def test_documented_command_uses_the_examples_own_contract(self) -> None:
        arguments = self._documented_arguments()
        self.assertEqual(arguments[0], "diff")
        self.assertEqual(arguments[arguments.index("--contract") + 1], "examples/collector-regression/contract.json")
        for flag in ("--contract", "--baseline", "--candidate"):
            self.assertTrue((ROOT / arguments[arguments.index(flag) + 1]).is_file(), flag)

    def test_documented_output_and_exit_status_match_the_tool(self) -> None:
        arguments = self._documented_arguments()
        resolved = [str(ROOT / value) if value.startswith("examples/") else value for value in arguments]
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
            status = main(resolved)
        self.assertEqual(status, EXIT_REGRESSION)
        self.assertIn(f"exited with status `{EXIT_REGRESSION}`", self.readme)
        self.assertEqual(output.getvalue(), _fenced_block(self.readme, "## Observed output", "text"))


if __name__ == "__main__":
    unittest.main()
