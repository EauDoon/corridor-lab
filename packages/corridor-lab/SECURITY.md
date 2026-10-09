# Security policy

Corridor Lab is an offline scenario calculator. Do not place real customer data,
account data, credentials, or production transaction records in its inputs.

The optional desktop interface reads only scenario or route files and folders
the user selects. It writes a report or scenario only after the user chooses
**Save Report...** or **Save Scenario As...** and a destination path. It has no
network requests, telemetry, datastore, subprocesses, or hidden writes.

## Reporting and supported versions

Report suspected vulnerabilities, and check which releases receive fixes, under
the repository security policy:
https://github.com/EauDoon/operator-labs/blob/main/SECURITY.md
