# Release checklist

Implementation, CI, packaging, and publication are separate states. This
checklist does not authorize a tag, release, or package-index upload.

Both packages share one version number (the lockstep policy) and are tagged
separately as `corridor-lab-vX.Y.Z` and `tracecanary-vX.Y.Z`.
`python tools/check_release.py` checks the versions, the pyproject dynamic
version, the package licenses, and the CHANGELOG structure; it runs in the
`Repo checks` workflow on every push and pull request. With
`--tag corridor-lab-vX.Y.Z` it also requires that the tag matches
`__version__` and that CHANGELOG.md has a dated `## [X.Y.Z]` section, and the
portable workflows run that check before building from a tag.
`python tools/check_release.py --notes X.Y.Z` prints that section for
`gh release create --notes-file`.

- [ ] Review the exact candidate diff and CHANGELOG.md's dated section for the release.
- [ ] Owner approves the version increments (both packages are currently 0.3.0).
      Keep package metadata and runtime versions aligned.
- [ ] Both package workflows and `Repo checks` pass on the exact candidate,
      including installed saved-project journeys outside the checkout with
      source imports excluded.
- [ ] Owner approves merging; record the resulting main SHA and its CI results.
- [ ] With separate authorization, build both portable Windows artifacts from
      that SHA. Verify each archive against its SHA-256 sidecar and confirm the
      built executable's timed headless smoke check passes.
- [ ] Record each artifact hash, Windows version, and actual window checks:
      launch without a separate Python install, create synthetic starters, run
      an investigation, save/reopen, export evidence, and close during work.
      A headless test or skipped display test does not satisfy this gate.
- [ ] Obtain explicit approval for tags (`corridor-lab-vX.Y.Z` and
      `tracecanary-vX.Y.Z`, annotated, on the same main commit). Tag
      workflows refuse a tag that disagrees with the package version or the
      CHANGELOG, and retain artifacts for 14 days; they do not create a
      durable GitHub Release.
- [ ] Obtain separate approval before a GitHub Release or package-index upload.
      If approved, verify the published bytes and hashes against the candidate.
- [ ] Record actual version, SHA, checks, artifact hashes, and publication state
      in CHANGELOG.md. Do not mark an unperformed gate complete.
