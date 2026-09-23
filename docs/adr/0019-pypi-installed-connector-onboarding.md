# ADR 0019: Present one pip-installed connector workflow on PyPI

- Status: Accepted
- Date: 2026-09-22

## Context

ADR 0018 separates the lightweight agent connector from the self-hosted service dependencies. Reusing the repository README as PyPI's package description exposed Docker deployment, editable source installation, `uvx`, and contributor workflows together. A connector user could install the package successfully and still encounter an unexplained `BOOTSTRAP_TOKEN` requirement by invoking the operator-only `init` command, or omit the required client argument from `connect`.

The generated connector configuration also invoked `uvx`, even when the user had deliberately installed the package with pip. That created a second runtime path and could download a different package version from the one the user had installed.

## Decision

Use `PYPI.md` as the Python distribution's long description. It documents one connector installation path:

1. install `provena-agent-memory` as a managed application with pipx;
2. obtain an API URL, agent credential, and exact scope from an operator, or self-host the released service stack and local Ollama configuration;
3. verify them with `provena doctor`; and
4. generate client configuration with `provena connect CLIENT`.

Keep the repository README as the complete operator and contributor guide. PyPI includes the minimal released Compose workflow needed for a connector user to become their own operator. It does not include source checkout or development setup commands.

`provena connect` resolves the `provena-mcp` executable installed in the current Python environment and writes that path into client configuration. It does not generate an `uvx` command. `provena init` remains an operator-only command against an already running service and continues to require `BOOTSTRAP_TOKEN`.

## Consequences

Package users get one connector installation and execution model, and the generated MCP configuration uses the exact pipx-managed environment. They can use an organization-operated service or run the versioned PostgreSQL, API, and Ollama containers themselves. Removing the pipx application invalidates the generated executable path; users must reinstall it and rerun `provena connect`.

The pip package remains a connector and does not bundle PostgreSQL, weaken bootstrap authorization, or collapse the service and connector dependency boundaries established by ADR 0018.

## Amendment: managed application installation

The primary public installation command is `pipx install provena-agent-memory`. pipx owns the isolated Python environment and exposes stable Provena commands on the user's path, so onboarding does not require manual virtual environment creation or activation. Regular pip remains supported for contributors and users who already manage a persistent environment. Ephemeral runners such as `pipx run` and `uvx` are unsuitable for installed lifecycle hooks because their executable paths may disappear between agent sessions.
