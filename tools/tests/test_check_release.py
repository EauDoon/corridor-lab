"""Unit tests for tools/check_release.py over small temporary repository trees."""

from __future__ import annotations

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))

import check_release  # noqa: E402

REPOSITORY = TOOLS.parent
LICENSE_TEXT = "MIT License\n\nCopyright (c) 2026 Example\n"
PYPROJECT = """[project]
name = "{package}"
dynamic = ["version"]

[tool.setuptools.dynamic]
version = {{attr = "{module}.__version__"}}
"""
CHANGELOG = """# Changelog

## [Unreleased]

### Added

- Something new.

## [0.2.0] - 2026-09-10

### Added

- A feature.

### Fixed

- A bug.

## [0.1.0] - 2026-08-02

### Added

- First release.

## Milestone history

### Added

Appendix headings may repeat names used above.

### Added

[Unreleased]: https://example.invalid/compare/v0.2.0...HEAD
[0.2.0]: https://example.invalid/compare/v0.1.0...v0.2.0
[0.1.0]: https://example.invalid/commit/abc1234
"""


class ReleaseTree:
    """A minimal monorepo tree with both packages at one version."""

    def __init__(self, root: Path, version: str = "0.2.0") -> None:
        self.root = root
        (root / "LICENSE").write_text(LICENSE_TEXT, encoding="utf-8", newline="\n")
        (root / "CHANGELOG.md").write_text(CHANGELOG, encoding="utf-8", newline="\n")
        for package, module in check_release.PACKAGES.items():
            source = root / "packages" / package / "src" / module
            source.mkdir(parents=True)
            self.set_version(package, version)
            (root / "packages" / package / "pyproject.toml").write_text(
                PYPROJECT.format(package=package, module=module), encoding="utf-8", newline="\n")
            (root / "packages" / package / "LICENSE").write_text(LICENSE_TEXT, encoding="utf-8", newline="\n")

    def set_version(self, package: str, version: str) -> None:
        module = check_release.PACKAGES[package]
        init = self.root / "packages" / package / "src" / module / "__init__.py"
        init.write_text(f'"""{package}."""\n\n__version__ = "{version}"\n', encoding="utf-8", newline="\n")

    def edit_changelog(self, old: str, new: str) -> None:
        path = self.root / "CHANGELOG.md"
        text = path.read_text(encoding="utf-8")
        assert old in text, old
        path.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")


class CheckReleaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.tree = ReleaseTree(Path(self._temporary.name))

    def tearDown(self) -> None:
        self._temporary.cleanup()

    def run_main(self, *arguments: str) -> tuple[int, str, str]:
        output, error = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
            try:
                status = check_release.main(["--root", str(self.tree.root), *arguments])
            except SystemExit as exc:
                status = int(exc.code)
        return status, output.getvalue(), error.getvalue()

    def assert_fails(self, needle: str, *arguments: str) -> None:
        status, output, error = self.run_main(*arguments)
        self.assertEqual(status, check_release.EXIT_MISMATCH, error)
        self.assertEqual(output, "")
        self.assertIn(needle, error)

    def test_a_consistent_tree_passes(self) -> None:
        status, output, error = self.run_main()
        self.assertEqual((status, error), (0, ""))
        self.assertEqual(output, "release metadata ok: corridor-lab 0.2.0, tracecanary 0.2.0\n")

    def test_a_matching_tag_passes_for_either_package(self) -> None:
        for tag in ("corridor-lab-v0.2.0", "tracecanary-v0.2.0"):
            with self.subTest(tag=tag):
                status, output, error = self.run_main("--tag", tag)
                self.assertEqual((status, error), (0, ""))
                self.assertIn(f"tag {tag} matches", output)

    def test_tag_version_must_match_the_package(self) -> None:
        self.assert_fails("names 9.9.9, but corridor-lab __version__ is 0.2.0", "--tag", "corridor-lab-v9.9.9")

    def test_tag_needs_a_dated_changelog_section(self) -> None:
        self.tree.set_version("corridor-lab", "0.3.0")
        self.tree.set_version("tracecanary", "0.3.0")
        self.assert_fails("no dated ## [0.3.0]", "--tag", "corridor-lab-v0.3.0")

    def test_malformed_and_unknown_package_tags_fail(self) -> None:
        for tag in ("v0.2.0", "corridor-lab-0.2.0", "corridor-lab-v0.2", "operator-labs-v0.2.0", "tracecanary-v0.2.0-rc1"):
            with self.subTest(tag=tag):
                self.assert_fails("must be corridor-lab-vX.Y.Z or tracecanary-vX.Y.Z", "--tag", tag)

    def test_lockstep_drift_fails(self) -> None:
        self.tree.set_version("tracecanary", "0.2.1")
        self.assert_fails("lockstep policy: both packages must share one version (corridor-lab 0.2.0, tracecanary 0.2.1)")

    def test_malformed_version_fails(self) -> None:
        for version in ("0.2", "v0.2.0", "0.2.0rc1"):
            with self.subTest(version=version):
                self.tree.set_version("corridor-lab", version)
                self.tree.set_version("tracecanary", version)
                self.assert_fails("is not an X.Y.Z version")

    def test_a_static_pyproject_version_fails(self) -> None:
        path = self.tree.root / "packages" / "tracecanary" / "pyproject.toml"
        path.write_text('[project]\nname = "tracecanary"\nversion = "0.2.0"\n', encoding="utf-8")
        status, _, error = self.run_main()
        self.assertEqual(status, check_release.EXIT_MISMATCH)
        self.assertIn("tracecanary: pyproject.toml declares a static version", error)
        self.assertIn('version must be {attr = "tracecanary.__version__"}', error)

    def test_license_drift_fails_but_line_endings_do_not(self) -> None:
        crlf = self.tree.root / "packages" / "corridor-lab" / "LICENSE"
        crlf.write_bytes(LICENSE_TEXT.replace("\n", "\r\n").encode("utf-8"))
        self.assertEqual(self.run_main()[0], 0)
        (self.tree.root / "packages" / "tracecanary" / "LICENSE").write_text("Apache License\n", encoding="utf-8")
        self.assert_fails("packages/tracecanary/LICENSE differs from the root LICENSE")

    def test_a_repeated_subsection_fails_outside_the_appendix(self) -> None:
        self.tree.edit_changelog("### Fixed\n\n- A bug.", "### Added\n\n- A bug.")
        self.assert_fails("section [0.2.0] repeats '### Added'")

    def test_a_missing_link_reference_fails(self) -> None:
        self.tree.edit_changelog("[0.1.0]: https://example.invalid/commit/abc1234\n", "")
        self.assert_fails("section [0.1.0] has no [0.1.0]: link reference")

    def test_unreleased_must_appear_exactly_once_and_first(self) -> None:
        self.tree.edit_changelog("## [Unreleased]\n", "## [Unreleased]\n\n## [Unreleased]\n")
        self.assert_fails("exactly one ## [Unreleased] section (found 2)")

    def test_version_sections_need_dates_and_descending_order(self) -> None:
        self.tree.edit_changelog("## [0.1.0] - 2026-08-02", "## [0.3.0] - 2026-08-02")
        self.tree.edit_changelog("[0.1.0]: ", "[0.3.0]: ")
        self.assert_fails("section [0.3.0] is out of descending order")
        self.tree.edit_changelog("## [0.2.0] - 2026-09-10", "## [0.2.0]")
        self.assert_fails("section [0.2.0] needs a ' - YYYY-MM-DD' release date")

    def test_print_version_and_usage_errors(self) -> None:
        status, output, error = self.run_main("--print-version", "tracecanary")
        self.assertEqual((status, output, error), (0, "0.2.0\n", ""))
        self.assertEqual(self.run_main("--print-version", "unknown")[0], check_release.EXIT_USAGE)
        self.assertEqual(self.run_main("--tag", "corridor-lab-v0.2.0", "--notes", "0.2.0")[0], check_release.EXIT_USAGE)

    def test_notes_print_one_section_body(self) -> None:
        status, output, error = self.run_main("--notes", "0.2.0")
        self.assertEqual((status, error), (0, ""))
        self.assertEqual(output, "### Added\n\n- A feature.\n\n### Fixed\n\n- A bug.\n")
        self.assert_fails("no ## [9.9.9] section", "--notes", "9.9.9")


class RepositoryTests(unittest.TestCase):
    def test_this_repository_passes(self) -> None:
        self.assertEqual(check_release.repository_problems(REPOSITORY), [])
        versions = {package: check_release.read_version(REPOSITORY, package) for package in check_release.PACKAGES}
        self.assertEqual(len(set(versions.values())), 1)


if __name__ == "__main__":
    unittest.main()
