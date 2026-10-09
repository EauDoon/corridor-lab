# TraceCanary release process

What each version changed is recorded in the repository
[CHANGELOG](../../../CHANGELOG.md). The approval gates are in the
[release checklist](../../../RELEASE-CHECKLIST.md), and
`tools/check_release.py` enforces the version, license, and CHANGELOG rules.

TraceCanary and Corridor Lab share one version number (the lockstep policy),
but each has its own distribution and tag. A release of this package is the
annotated tag `tracecanary-vX.Y.Z` on a `main` commit whose
`tracecanary.__version__` is `X.Y.Z` and whose CHANGELOG has a dated
`## [X.Y.Z]` section. A release build must run from a clean checkout on
Windows and Ubuntu with Python 3.11 or newer.

The portable Windows GUI artifact is built by
`.github/workflows/tracecanary-portable-windows.yml`. It runs on that tag, on
manual dispatch, and on pull requests that change how the executable is
built. On a tag it first runs
`python tools/check_release.py --tag tracecanary-vX.Y.Z` and stops before any
build when the tag, the package version, or the CHANGELOG disagree. It then
builds the wheel and sdist with the pinned setuptools, builds
`TraceCanary.pyw` in windowed mode with the pinned PyInstaller, archives the
executable, and writes a SHA-256 sidecar.

The workflow retains `TraceCanary-X.Y.Z-windows-x64.zip` with its sidecar, plus
`tracecanary-X.Y.Z-dist` (wheel, sdist, and `SHA256SUMS`), as run artifacts for
14 days. It does not create a GitHub Release or publish the files
automatically.

Before a maintainer creates a tag, run the full unit suite, the CLI smoke check,
the GUI smoke check, and the batch SARIF and JUnit checks. Verify the downloaded
archive against its sidecar. Remote publication and release creation remain
separate approved actions.

The executable is smoke-tested with a 60-second deadline before packaging.
This headless check does not prove window interaction. Use the release
checklist to record actual Windows interaction at the exact artifact hash
before approving a release.
