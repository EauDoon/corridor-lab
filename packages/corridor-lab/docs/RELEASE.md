# Corridor Lab release notes

## v0.2.0 preparation

Version 0.2.0 adds signed guardrail headroom, a weighted outcome ledger, deadline/resolution profiles, whole-volume break-even checks, and bounded transaction grids. Existing route evaluation and ranking semantics remain unchanged.

The portable Windows GUI workflow is `.github/workflows/corridor-lab-portable-windows.yml`.
It builds the windowed `CorridorLab.pyw` launcher with pinned tools, writes a
SHA-256 sidecar, and retains both files as run artifacts for 14 days. The
workflow does not create or publish a remote release. A maintainer must run the
full tests, GUI smoke check, and report format checks, then verify the downloaded
archive against its sidecar before separately approving publication.

The executable is smoke-tested with a 60-second deadline before packaging.
This headless check does not prove window interaction. Use the repository
[release checklist](../../../RELEASE-CHECKLIST.md) to record actual Windows
interaction at the exact artifact hash before approving a release.
