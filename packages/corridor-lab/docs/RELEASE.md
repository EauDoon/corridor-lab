# Corridor Lab release process

What each version changed is recorded in the repository
[CHANGELOG](../../../CHANGELOG.md). The approval gates are in the
[release checklist](../../../RELEASE-CHECKLIST.md), and
`tools/check_release.py` enforces the version, license, and CHANGELOG rules.

Corridor Lab and TraceCanary share one version number (the lockstep policy),
but each has its own distribution and tag. A release of this package is the
annotated tag `corridor-lab-vX.Y.Z` on a `main` commit whose
`corridor_lab.__version__` is `X.Y.Z` and whose CHANGELOG has a dated
`## [X.Y.Z]` section.

The portable Windows GUI workflow is `.github/workflows/corridor-lab-portable-windows.yml`.
It runs on that tag, on manual dispatch, and on pull requests that change how
the executable is built. On a tag it first runs
`python tools/check_release.py --tag corridor-lab-vX.Y.Z` and stops before any
build when the tag, the package version, or the CHANGELOG disagree. It then
builds the wheel and sdist with the pinned setuptools, builds the windowed
`CorridorLab.pyw` launcher with pinned PyInstaller, and retains
`CorridorLab-X.Y.Z-windows-x64.zip` with its SHA-256 sidecar, plus
`corridor-lab-X.Y.Z-dist` (wheel, sdist, and `SHA256SUMS`), as run artifacts
for 14 days. The workflow does not create or publish a remote release. A
maintainer must run the full tests, GUI smoke check, and report format checks,
then verify the downloaded archive against its sidecar before separately
approving publication.

The executable is smoke-tested with a 60-second deadline before packaging.
This headless check does not prove window interaction. Use the release
checklist to record actual Windows interaction at the exact artifact hash
before approving a release.
