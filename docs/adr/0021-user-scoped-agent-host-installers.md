# ADR 0021: User-scoped agent host installers

- Status: Accepted
- Date: 2026-09-25
- Extends: ADR 0014 and ADR 0020

## Context

Provena's MCP server and lifecycle command adapters already normalize Codex, Claude Code, and Gemini CLI events, but one-command installation existed only for Codex. Printing generic MCP JSON is insufficient for automatic memory because MCP tool availability does not guarantee that a model retrieves context or records both sides of every conversation. Each host also uses different configuration files, event names, timeout units, and background-hook capabilities.

The safe onboarding boundary from ADR 0020 still applies: installing the Python package alone must not edit another application's configuration or begin recording conversations. Credentials must not be copied into multiple host files, and an installer must preserve unrelated user configuration.

## Decision

`provena quickstart HOST` and `provena connect HOST --install` support `codex`, `claude`, and `gemini`. The quickstart service, PostgreSQL store, tenant scope, credentials, local Ollama models, and operator console remain shared. The selected host changes only the local adapter installation.

Each host receives a protected connection document at the user configuration boundary:

- Codex: `${XDG_CONFIG_HOME:-~/.config}/provena/codex.json`
- Claude Code: `${XDG_CONFIG_HOME:-~/.config}/provena/claude.json`
- Gemini CLI: `${XDG_CONFIG_HOME:-~/.config}/provena/gemini.json`

The document has mode `0600` and contains the API URL, agent credential, exact scope, and host provenance label. MCP and hook configuration reference that file by path and do not contain the credential.

Installers merge one user-scoped `provena` MCP server and Provena-owned hooks into the host's native configuration while preserving unrelated keys, servers, and handlers:

- Codex uses `~/.codex/config.toml` and `~/.codex/hooks.json` through the existing Codex CLI integration.
- Claude Code uses the top-level user `mcpServers` entry in `~/.claude.json` and hooks in `~/.claude/settings.json`. `CLAUDE_CONFIG_DIR` is honored.
- Gemini CLI uses `mcpServers` and hooks in `~/.gemini/settings.json`. `GEMINI_CLI_HOME` is honored.

Claude Code maps prompt and response capture to `UserPromptSubmit` and `Stop`. Gemini CLI maps them to `BeforeAgent` and `AfterAgent`. Retrieval runs before the agent turn and returns explicitly untrusted, attributed context. Capture records immutable events and requests candidate fact extraction. Hook failures remain fail-open and cannot block an agent turn through Provena policy.

Re-running an installer replaces only Provena's MCP entry and Provena-owned handlers. Existing connection files from any supported host may be reused by quickstart when they authenticate to the running local service, which avoids creating a second organization when a user adds another host.

## Consequences

Codex, Claude Code, and Gemini CLI have the same two-command local onboarding path and can share facts through the same organization and exact scope. Host session IDs remain provenance attributes rather than visibility boundaries.

Claude Code supports asynchronous command hooks, matching the existing Codex capture behavior. Gemini CLI currently documents synchronous command hooks, so its capture hook may remain active while local extraction completes. The timeout is expressed in Gemini's required milliseconds and the hook remains fail-open. Moving extraction into a durable server-side job would change the processing architecture and requires a separate decision.

Direct JSON updates are atomic, use mode `0600`, and preserve unrelated configuration, but a host process already running will not see every change until restarted. Managed enterprise settings may override user settings; the installer does not bypass host policy.
