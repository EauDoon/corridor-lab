from __future__ import annotations

import sys
import unittest
from pathlib import Path

import tomllib

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import tracecanary

ROOT = Path(__file__).resolve().parents[1]


class MetadataTests(unittest.TestCase):
    def test_gui_entrypoint_and_public_urls_are_declared(self) -> None:
        metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        project = metadata["project"]
        self.assertEqual(project["gui-scripts"]["tracecanary-gui"], "tracecanary.gui:main")
        self.assertEqual(
            project["urls"],
            {
                "Source": "https://github.com/EauDoon/operator-labs/tree/main/packages/tracecanary",
                "Issues": "https://github.com/EauDoon/operator-labs/issues",
                "Security": "https://github.com/EauDoon/operator-labs/blob/main/packages/tracecanary/SECURITY.md",
                "Documentation": "https://github.com/EauDoon/operator-labs/tree/main/packages/tracecanary#readme",
            },
        )

    def test_version_is_single_sourced_from_the_package(self) -> None:
        metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertNotIn("version", metadata["project"])
        self.assertIn("version", metadata["project"]["dynamic"])
        self.assertEqual(metadata["tool"]["setuptools"]["dynamic"]["version"], {"attr": "tracecanary.__version__"})
        self.assertRegex(tracecanary.__version__, r"^\d+\.\d+\.\d+$")

    def test_license_is_an_spdx_expression_with_its_file(self) -> None:
        project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
        self.assertEqual(project["license"], "MIT")
        self.assertEqual(project["license-files"], ["LICENSE"])
        # License classifiers are deprecated alongside table-form licenses.
        self.assertFalse([item for item in project["classifiers"] if item.startswith("License ::")])

    def test_shipped_license_text_is_mit(self) -> None:
        text = (ROOT / "LICENSE").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("MIT License"))
        self.assertIn("Copyright (c) 2026 EauDoon", text)
