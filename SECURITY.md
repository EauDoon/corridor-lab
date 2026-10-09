# Security

This is the single security policy for both packages in this repository,
Corridor Lab and TraceCanary. Each package's own `SECURITY.md` describes its
security boundary and links here for reporting.

## Reporting a vulnerability

Use GitHub private vulnerability reporting (the **Report a vulnerability**
button on this repository's Security tab) when it is enabled.

If that button is not available, open a public issue that asks a maintainer
for a private contact. Put no technical detail in that issue: no description
of the flaw, no reproduction, and no affected command. Share the details only
after a private channel exists.

Include the following in your private report:

- A clear description of the issue and its impact.
- The affected package and the output of `corridorlab --version` or
  `tracecanary --version`.
- A minimal synthetic reproduction and the command used.
- Any known mitigations or workarounds.

Never include real customer, payment, or account data, real trace payloads,
secrets, access tokens, personal data, or matched canary values.

We aim to acknowledge new reports within five business days. A maintainer will
follow up to coordinate disclosure and a fix timeline.

## Supported versions

Security fixes target the latest minor release of each package. Older
releases are not patched; please upgrade before reporting.

## Disclosure policy

We follow coordinated disclosure. Please give us a reasonable window to
investigate and ship a fix before public disclosure.
