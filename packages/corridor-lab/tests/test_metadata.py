import contextlib
import io
import tomllib
import unittest
from pathlib import Path

import corridor_lab
from corridor_lab.cli import main as cli_main
from corridor_lab.gui import main as gui_main

PACKAGE = Path(__file__).resolve().parents[1]


class MetadataTests(unittest.TestCase):
    """Packaging metadata that wheels and sdists carry to users."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.metadata = tomllib.loads((PACKAGE / "pyproject.toml").read_text(encoding="utf-8"))
        cls.project = cls.metadata["project"]

    def test_version_is_single_sourced_from_the_package(self) -> None:
        self.assertNotIn("version", self.project)
        self.assertIn("version", self.project["dynamic"])
        self.assertEqual(self.metadata["tool"]["setuptools"]["dynamic"]["version"], {"attr": "corridor_lab.__version__"})
        self.assertRegex(corridor_lab.__version__, r"^\d+\.\d+\.\d+$")

    def test_cli_and_gui_report_the_package_version(self) -> None:
        # corridorlab's main lets argparse exit, so --version raises SystemExit(0).
        for entry, prog in ((cli_main, "corridorlab"), (gui_main, "corridorlab-gui")):
            output = io.StringIO()
            with self.subTest(prog=prog), contextlib.redirect_stdout(output), self.assertRaises(SystemExit) as raised:
                entry(["--version"])
            self.assertEqual(raised.exception.code, 0)
            self.assertEqual(output.getvalue(), f"{prog} {corridor_lab.__version__}\n")

    def test_license_is_an_spdx_expression_with_its_file(self) -> None:
        self.assertEqual(self.project["license"], "MIT")
        self.assertEqual(self.project["license-files"], ["LICENSE"])
        # License classifiers are deprecated alongside table-form licenses.
        self.assertFalse([item for item in self.project["classifiers"] if item.startswith("License ::")])

    def test_shipped_license_text_is_mit(self) -> None:
        text = (PACKAGE / "LICENSE").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("MIT License"))
        self.assertIn("Copyright (c) 2026 EauDoon", text)


if __name__ == "__main__":
    unittest.main()
