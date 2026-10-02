# TraceCanary release notes

## v0.2.0 preparation

Version 0.2.0 adds value-free contract inspection, exact coverage gates and comparisons, missing-retention matrices, and weighted batch coverage. Existing check and diff semantics remain unchanged. A release build must run from a clean checkout on Windows and Ubuntu with Python 3.11 or newer.

The portable Windows GUI artifact is built by
`.github/workflows/tracecanary-portable-windows.yml`. The workflow installs the exact
package and PyInstaller versions, builds `TraceCanary.pyw` in windowed mode,
archives the executable, and writes a SHA-256 sidecar.

The workflow retains the archive and sidecar as run artifacts for 14 days. It
does not create a GitHub Release or publish the files automatically.

Before a maintainer creates a tag, run the full unit suite, the CLI smoke check,
the GUI smoke check, and the batch SARIF and JUnit checks. Verify the downloaded
archive against its sidecar. Remote publication and release creation remain
separate approved actions.

The executable is smoke-tested with a 60-second deadline before packaging.
This headless check does not prove window interaction. Use the repository
[release checklist](../../../RELEASE-CHECKLIST.md) to record actual Windows
interaction at the exact artifact hash before approving a release.
