# ADR 0020: One-command local onboarding and default host memory

- Status: Accepted
- Date: 2026-09-23
- Supersedes: ADR 0011 only for the Codex installation experience

## Context

The published Python package already contains the MCP connector and portable capture and retrieval hooks, but users must separately download deployment files, generate service secrets, start containers, bootstrap credentials, edit Codex MCP configuration, create hook configuration, and start the console. This makes the safe path harder than a partial MCP-only connection. MCP instructions can request retrieval, but model compliance is not a reliable lifecycle integration and MCP alone cannot passively observe both sides of a conversation.

Automatic capture has privacy and trust consequences. A Python package installation must not silently alter agent configuration or begin recording conversations. At the same time, a user who explicitly connects Provena expects memory to work on ordinary prompts without repeatedly naming Provena.

## Decision

The PyPI package provides two explicit setup commands:

- `provena quickstart codex` prepares the version-matched local Compose deployment, preserves an existing environment and PostgreSQL volume, bootstraps separate agent and human credentials, configures Codex MCP and lifecycle hooks, starts local Ollama, and starts the operator console.
- `provena connect codex --install` configures MCP and lifecycle hooks for a running operator-provided or self-hosted service.

Running either command is the user's opt-in boundary. After that boundary, automatic retrieval and capture are the default for Codex turns in the configured scope. `UserPromptSubmit` retrieves relevant claims synchronously and captures the user turn asynchronously. `Stop` captures the final assistant response asynchronously. Hook failures remain fail-open and cannot reject an agent turn.

Credentials are stored once in a mode `0600` JSON connection file under the user's configuration directory. Codex MCP and hook definitions reference that file and do not duplicate the API key. The installer merges hook configuration, preserves unrelated handlers, replaces earlier Provena handlers idempotently, and relies on Codex's required hook trust review.

The raw user and assistant turns remain immutable evidence because provenance cannot be reconstructed from extracted facts alone. Extraction creates low-authority candidate claims. Automatic capture never promotes a claim, raises source authority, grants action authority, or treats retrieved content as instructions.

`pip install` itself has no configuration side effects. It cannot know the desired tenant, scope, service, credentials, or host consent, and package installers must not mutate unrelated application configuration.

## Consequences

The common local path becomes two commands: install the package, then run quickstart. Users must still review and trust the installed Codex hooks through `/hooks`, as required by Codex. The first local run may take several minutes while Ollama downloads models.

Automatic memory remains explicitly enabled per host installation while becoming the default behavior after that installation. Other hosts keep the portable MCP and hook boundaries from ADR 0014 until equivalent safe installers are implemented.
