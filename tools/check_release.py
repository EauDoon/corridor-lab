"""Release metadata gate for the Operator Labs monorepo.

Standard library only; runs on Python 3.11 or newer from any working directory.

    python tools/check_release.py                       check the repository
    python tools/check_release.py --tag NAME            also check a release tag
    python tools/check_release.py --print-version PKG   print a package version
    python tools/check_release.py --notes VERSION       print a CHANGELOG section

The default checks are:

- each package's ``__version__`` is a literal ``X.Y.Z`` (read with ``ast``,
  never imported);
- both packages share one version (the lockstep policy);
- each ``pyproject.toml`` takes its version from ``__version__`` through
  ``[tool.setuptools.dynamic]`` and declares no static version;
- each package ``LICENSE`` equals the root ``LICENSE``, ignoring CRLF;
- ``CHANGELOG.md`` has exactly one ``## [Unreleased]`` section above dated
  ``## [X.Y.Z] - YYYY-MM-DD`` sections in descending order, every such
  heading has a link reference, and no ``### `` subsection repeats inside a
  section. Sections after the last version section are appendices.

``--tag`` requires ``corridor-lab-vX.Y.Z`` or ``tracecanary-vX.Y.Z`` whose
version equals that package's ``__version__`` and has a dated CHANGELOG
section. Exit status: 0 when every check passes, 1 when a check fails, and
2 for a usage error.
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

PACKAGES = {"corridor-lab": "corridor_lab", "tracecanary": "tracecanary"}
VERSION = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
TAG = re.compile(r"^(?P<package>corridor-lab|tracecanary)-v(?P<version>\d+\.\d+\.\d+)$")
SECTION = re.compile(r"^## \[(?P<name>[^\]]+)\](?P<rest>.*)$")
DATED = re.compile(r"^ - (?P<date>\d{4}-\d{2}-\d{2})$")
LINK = re.compile(r"^\[(?P<name>[^\]]+)\]: (?P<url>\S+)$")
DEFAULT_ROOT = Path(__file__).resolve().parents[1]

EXIT_OK = 0
EXIT_MISMATCH = 1
EXIT_USAGE = 2


class ReleaseError(Exception):
    """A release metadata check failed."""


@dataclass
class Section:
    name: str
    date: str | None
    line: int
    body: list[str] = field(default_factory=list)


@dataclass
class Changelog:
    sections: list[Section]
    links: dict[str, str]
    problems: list[str]


def read_version(root: Path, package: str) -> str:
    """Return the literal ``__version__`` of a package without importing it."""
    path = root / "packages" / package / "src" / PACKAGES[package] / "__init__.py"
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError) as exc:
        raise ReleaseError(f"{package}: cannot read {path.as_posix()}: {exc}") from exc
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "__version__" for target in node.targets):
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                return node.value.value
            raise ReleaseError(f"{package}: __version__ must be a string literal")
    raise ReleaseError(f"{package}: no __version__ assignment in {path.as_posix()}")


def _version_key(version: str) -> tuple[int, int, int]:
    match = VERSION.match(version)
    if match is None:
        raise ReleaseError(f"not an X.Y.Z version: {version!r}")
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def parse_changelog(text: str) -> Changelog:
    """Split CHANGELOG.md into bracketed sections and link references."""
    sections: list[Section] = []
    links: dict[str, str] = {}
    problems: list[str] = []
    current: Section | None = None
    fenced = False
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.rstrip()
        if line.startswith("```"):
            fenced = not fenced
        if not fenced:
            link = LINK.match(line)
            if link is not None:
                if link.group("name") in links:
                    problems.append(f"CHANGELOG.md:{number}: duplicate link reference [{link.group('name')}]")
                links[link.group("name")] = link.group("url")
                continue
            if line.startswith("## "):
                heading = SECTION.match(line)
                if heading is None:
                    current = None  # an appendix such as the milestone history
                    continue
                rest = heading.group("rest")
                dated = DATED.match(rest)
                if rest and dated is None:
                    problems.append(f"CHANGELOG.md:{number}: malformed section heading {line!r}")
                current = Section(heading.group("name"), dated.group("date") if dated else None, number)
                sections.append(current)
                continue
        if current is not None:
            current.body.append(raw)
    return Changelog(sections, links, problems)


def changelog_problems(changelog: Changelog) -> list[str]:
    problems = list(changelog.problems)
    names = [section.name for section in changelog.sections]
    if names.count("Unreleased") != 1:
        problems.append(f"CHANGELOG.md must have exactly one ## [Unreleased] section (found {names.count('Unreleased')})")
    elif names[0] != "Unreleased":
        problems.append("CHANGELOG.md: ## [Unreleased] must come before every version section")
    previous: tuple[int, int, int] | None = None
    for section in changelog.sections:
        if section.name != "Unreleased":
            if VERSION.match(section.name) is None:
                problems.append(f"CHANGELOG.md:{section.line}: section [{section.name}] is not an X.Y.Z version")
                continue
            if section.date is None:
                problems.append(f"CHANGELOG.md:{section.line}: section [{section.name}] needs a ' - YYYY-MM-DD' release date")
            key = _version_key(section.name)
            if previous is not None and key >= previous:
                problems.append(f"CHANGELOG.md:{section.line}: section [{section.name}] is out of descending order")
            previous = key
        if section.name not in changelog.links:
            problems.append(f"CHANGELOG.md: section [{section.name}] has no [{section.name}]: link reference")
        seen: set[str] = set()
        fenced = False
        for line in section.body:
            if line.startswith("```"):
                fenced = not fenced
            if fenced or not line.startswith("### "):
                continue
            subsection = line[4:].strip()
            if subsection in seen:
                problems.append(f"CHANGELOG.md: section [{section.name}] repeats '### {subsection}'")
            seen.add(subsection)
    return problems


def repository_problems(root: Path) -> list[str]:
    """Run every default check and return the problems found."""
    problems: list[str] = []
    versions: dict[str, str] = {}
    for package, module in PACKAGES.items():
        try:
            version = read_version(root, package)
        except ReleaseError as exc:
            problems.append(str(exc))
            continue
        if VERSION.match(version) is None:
            problems.append(f"{package}: __version__ {version!r} is not an X.Y.Z version")
        versions[package] = version
        pyproject = root / "packages" / package / "pyproject.toml"
        try:
            metadata = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError) as exc:
            problems.append(f"{package}: cannot read pyproject.toml: {exc}")
        else:
            project = metadata.get("project", {})
            if "version" in project:
                problems.append(f"{package}: pyproject.toml declares a static version; use dynamic = [\"version\"]")
            if "version" not in project.get("dynamic", []):
                problems.append(f"{package}: pyproject.toml must list \"version\" in project.dynamic")
            attr = metadata.get("tool", {}).get("setuptools", {}).get("dynamic", {}).get("version", {}).get("attr")
            if attr != f"{module}.__version__":
                problems.append(f"{package}: [tool.setuptools.dynamic] version must be {{attr = \"{module}.__version__\"}}")
        try:
            root_license = (root / "LICENSE").read_bytes().replace(b"\r\n", b"\n")
            package_license = (root / "packages" / package / "LICENSE").read_bytes().replace(b"\r\n", b"\n")
        except OSError as exc:
            problems.append(f"{package}: cannot compare LICENSE files: {exc}")
        else:
            if package_license != root_license:
                problems.append(f"{package}: packages/{package}/LICENSE differs from the root LICENSE")
    if len(set(versions.values())) > 1:
        detail = ", ".join(f"{package} {version}" for package, version in versions.items())
        problems.append(f"lockstep policy: both packages must share one version ({detail})")
    try:
        changelog = parse_changelog((root / "CHANGELOG.md").read_text(encoding="utf-8"))
    except OSError as exc:
        problems.append(f"cannot read CHANGELOG.md: {exc}")
    else:
        problems.extend(changelog_problems(changelog))
    return problems


def tag_problems(root: Path, tag: str) -> list[str]:
    match = TAG.match(tag)
    if match is None:
        return [f"tag {tag!r} must be corridor-lab-vX.Y.Z or tracecanary-vX.Y.Z"]
    package, version = match.group("package"), match.group("version")
    problems: list[str] = []
    try:
        declared = read_version(root, package)
    except ReleaseError as exc:
        return [str(exc)]
    if declared != version:
        problems.append(f"tag {tag} names {version}, but {package} __version__ is {declared}")
    try:
        changelog = parse_changelog((root / "CHANGELOG.md").read_text(encoding="utf-8"))
    except OSError as exc:
        return problems + [f"cannot read CHANGELOG.md: {exc}"]
    dated = [section for section in changelog.sections if section.name == version and section.date is not None]
    if not dated:
        problems.append(f"CHANGELOG.md has no dated ## [{version}] - YYYY-MM-DD section for tag {tag}")
    return problems


def release_notes(root: Path, version: str) -> str:
    """Return the body of one CHANGELOG section, for gh release create --notes-file."""
    changelog = parse_changelog((root / "CHANGELOG.md").read_text(encoding="utf-8"))
    for section in changelog.sections:
        if section.name == version:
            lines = list(section.body)
            while lines and not lines[0].strip():
                lines.pop(0)
            while lines and not lines[-1].strip():
                lines.pop()
            return "\n".join(lines) + "\n"
    raise ReleaseError(f"CHANGELOG.md has no ## [{version}] section")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="check_release.py", description="Check Operator Labs release metadata.")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="repository root (default: this checkout)")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--tag", help="also require this release tag to match its package version and CHANGELOG")
    mode.add_argument("--print-version", choices=sorted(PACKAGES), help="print one package's __version__")
    mode.add_argument("--notes", metavar="VERSION", help="print the CHANGELOG section for VERSION")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root: Path = args.root
    try:
        if args.print_version:
            version = read_version(root, args.print_version)
            if VERSION.match(version) is None:
                raise ReleaseError(f"{args.print_version}: __version__ {version!r} is not an X.Y.Z version")
            print(version)
            return EXIT_OK
        if args.notes:
            sys.stdout.write(release_notes(root, args.notes))
            return EXIT_OK
    except ReleaseError as exc:
        print(f"check_release: {exc}", file=sys.stderr)
        return EXIT_MISMATCH
    problems = repository_problems(root)
    if args.tag:
        problems.extend(tag_problems(root, args.tag))
    for problem in problems:
        print(f"check_release: {problem}", file=sys.stderr)
    if problems:
        return EXIT_MISMATCH
    versions = ", ".join(f"{package} {read_version(root, package)}" for package in PACKAGES)
    suffix = f"; tag {args.tag} matches" if args.tag else ""
    print(f"release metadata ok: {versions}{suffix}")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
