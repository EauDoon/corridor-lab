# Release checklist

Implementation, CI, packaging, and publication are separate states. This
checklist does not authorize a tag, release, or package-index upload.

- [ ] Review the exact candidate diff and CHANGELOG.md's Unreleased section.
- [ ] Owner approves the version increments (both packages are currently 0.2.0;
      the draft proposes 0.3.0). Keep package metadata and runtime versions aligned.
- [ ] Both package workflows pass on the exact candidate, including installed
      saved-project journeys outside the checkout with source imports excluded.
- [ ] Owner approves merging; record the resulting main SHA and its CI results.
- [ ] With separate authorization, build both portable Windows artifacts from
      that SHA. Verify each archive against its SHA-256 sidecar and confirm the
      built executable's timed headless smoke check passes.
- [ ] Record each artifact hash, Windows version, and actual window checks:
      launch without a separate Python install, create synthetic starters, run
      an investigation, save/reopen, export evidence, and close during work.
      A headless test or skipped display test does not satisfy this gate.
- [ ] Obtain explicit approval for tags (`corridor-lab-v0.x.y` and
      `tracecanary-v0.x.y`). Tag workflows retain artifacts for 14 days; they do
      not create a durable GitHub Release.
- [ ] Obtain separate approval before a GitHub Release or package-index upload.
      If approved, verify the published bytes and hashes against the candidate.
- [ ] Record actual version, SHA, checks, artifact hashes, and publication state
      in CHANGELOG.md. Do not mark an unperformed gate complete.
