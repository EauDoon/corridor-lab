# Contributing

Thanks for your interest in operator-labs. Pull requests are welcome.

## Before you open a pull request

- Open an issue first for any non-trivial change so we can agree on direction.
- Keep changes focused. One logical change per pull request.
- Follow the existing code style and project layout.

## Requirements

- Tests are required for new behavior and bug fixes. Update existing tests when
  behavior changes.
- Continuous integration must be green before review. CI runs each package's
  unit tests on Linux, Windows, and macOS for Python 3.11 through 3.14, builds
  and installs the wheel in an isolated environment, runs the installed
  journeys and GUI smoke tests, builds and tests the sdist, and lints the whole
  repository with pinned ruff. There is no type checker in CI.
- Both packages use only the Python standard library at runtime. Do not add
  runtime dependencies.
- Commits should be signed when possible and messages should follow the
  Conventional Commits style.

## Local checks

Run the same checks CI runs before pushing. Python 3.11 or newer is required.

From `packages/corridor-lab`:

```text
PYTHONPATH=src python -m unittest discover -s tests -v
python -m compileall -q src
PYTHONPATH=src python -m corridor_lab.gui --smoke-test
```

From `packages/tracecanary`:

```text
python -m unittest discover -s tests -v
python -m compileall -q src
PYTHONPATH=src python -m tracecanary.gui --smoke-test
```

From the repository root, with `ruff==0.16.10` installed:

```text
ruff check .
```

In PowerShell, set `$env:PYTHONPATH = "src"` instead of the `PYTHONPATH=src`
prefix. To check the installed wheel as CI does, build it with the pinned
`setuptools==83.0.0`, install it into a fresh virtual environment, and run
`python -I tests/installed_journey.py` from outside the checkout with
`PYTHONPATH` unset.

## Review process

A maintainer will review for correctness, tests, and fit with project goals.
Small fixes may be merged quickly. Larger changes go through more rounds.

## Code of conduct

Be respectful. Assume good intent. Focus on the work.
