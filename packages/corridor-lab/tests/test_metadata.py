import tomllib
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]


class MetadataTests(unittest.TestCase):
    """Packaging metadata that wheels and sdists carry to users."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.project = tomllib.loads((PACKAGE / "pyproject.toml").read_text(encoding="utf-8"))["project"]

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
