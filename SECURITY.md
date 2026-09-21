# Security policy

## Supported versions

Until Provena reaches 1.0, security fixes are applied to the latest released minor version.

## Reporting a vulnerability

Do not open a public issue for suspected vulnerabilities or tenant-isolation failures. Use GitHub's private vulnerability reporting feature on the repository Security tab and include:


- the affected version or commit;
- reproduction steps;
- the expected and observed security boundary; and
- any evidence that credentials or tenant data were exposed.

Do not include real API keys, memory content, or customer data. Revoke any credential that may have been disclosed.

## Deployment boundary

The release Compose files bind the API and console to loopback for local evaluation. Operators are responsible for TLS, network access control, backups, secret management, retention, and account erasure before exposing Provena to other users.

Memory content is untrusted data. A retrieved claim never grants permission to perform an action.
