# Security policy

TraceCanary accepts local JSON files only and makes no network requests. Its test data is synthetic.

## Reporting and supported versions

Report suspected vulnerabilities, and check which releases receive fixes, under the repository security policy: https://github.com/EauDoon/operator-labs/blob/main/SECURITY.md. Include a minimal synthetic reproduction, the output of `tracecanary --version`, the operating system, and the command used. Do not include real trace payloads, secrets, personal data, access tokens, or matched canary values.

## Security boundary

TraceCanary rejects duplicate JSON keys and applies configurable input-size, nesting, and batch-file limits. These controls reduce parser ambiguity and resource exhaustion risk; they are not a substitute for sandboxing untrusted files or applying process-level resource limits.

The tool reports exact configured synthetic canaries only. It does not validate redaction pipelines, discover arbitrary secrets, determine legal compliance, or certify a trace as safe.

The optional desktop GUI calls the same local library functions as the CLI. It makes no network requests, launches no subprocesses, and writes only after the user selects a destination in the `Save Report` dialog or explicitly selects an empty directory for synthetic starter files.
