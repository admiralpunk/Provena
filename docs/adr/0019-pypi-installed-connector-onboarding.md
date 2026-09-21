# ADR 0019: Present one pip-installed connector workflow on PyPI

- Status: Accepted
- Date: 2026-09-22

## Context

ADR 0018 separates the lightweight agent connector from the self-hosted service dependencies. Reusing the repository README as PyPI's package description exposed Docker deployment, editable source installation, `uvx`, and contributor workflows together. A connector user could install the package successfully and still encounter an unexplained `BOOTSTRAP_TOKEN` requirement by invoking the operator-only `init` command, or omit the required client argument from `connect`.

The generated connector configuration also invoked `uvx`, even when the user had deliberately installed the package with pip. That created a second runtime path and could download a different package version from the one the user had installed.

## Decision

Use `PYPI.md` as the Python distribution's long description. It documents one connector path:

1. install `provena-agent-memory` with pip;
2. obtain an API URL, agent credential, and exact scope from an operator;
3. verify them with `provena doctor`; and
4. generate client configuration with `provena connect CLIENT`.

Keep the repository README as the complete operator and contributor guide. PyPI may link to those server instructions, but it does not duplicate Docker, source checkout, or development setup commands.

`provena connect` resolves the `provena-mcp` executable installed in the current Python environment and writes that path into client configuration. It does not generate an `uvx` command. `provena init` remains an operator-only command against an already running service and continues to require `BOOTSTRAP_TOKEN`.

## Consequences

Package users get one installation and execution model, and the generated MCP configuration uses the exact installed environment. Moving or deleting that environment invalidates the generated executable path; users must keep it available or rerun `provena connect` after reinstalling.

The pip package remains a connector and does not bundle PostgreSQL, weaken bootstrap authorization, or collapse the service and connector dependency boundaries established by ADR 0018.
