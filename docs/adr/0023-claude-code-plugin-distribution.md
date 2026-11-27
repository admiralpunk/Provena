# ADR 0023: Claude Code plugin distribution

- Status: Proposed
- Date: 2026-11-27
- Extends: ADR 0019, ADR 0020, and ADR 0021

## Context

Claude Code users discover and install agent extensions through plugin marketplaces (`/plugin marketplace add OWNER/REPO`, then `/plugin install NAME@MARKETPLACE`). Today Provena reaches Claude Code only through `provena quickstart claude` or `provena connect claude --install`. Those commands merge a user-scoped MCP entry into `~/.claude.json` and hooks into `~/.claude/settings.json` (ADR 0021). That works, but users browsing plugins never see it, and plugins are where Claude Code memory tools are compared.

A Claude Code plugin can bundle an MCP server (`.mcp.json`), lifecycle hooks (`hooks/hooks.json`), and skills. Paths inside the plugin resolve through `${CLAUDE_PLUGIN_ROOT}`. A plugin cannot install Python packages, start Docker services, or create Provena credentials, so it can't replace quickstart.

The ADR 0021 boundaries still apply. Installing software must not silently begin recording. The agent credential lives in one protected connection file and is never copied into host configuration. Unrelated user configuration must be preserved.

## Decision

1. **The plugin is a thin adapter.** Ship a plugin named `provena` in `plugins/provena/`, and a marketplace file at `.claude-plugin/marketplace.json` with a matching entry whose `source` is `./plugins/provena`. The plugin contains:
   - `.mcp.json`: one stdio server that runs `provena-mcp --host claude`.
   - `hooks/hooks.json`: the same `UserPromptSubmit` (context, then asynchronous capture) and `Stop` (asynchronous capture) handlers that `build_provena_hooks` writes today, invoking `provena-agent-context --host claude` and `provena-agent-capture --host claude`.
   - Skills for read-only diagnostics such as status and explaining a claim. No skill can change claim status, because agent credentials cannot promote claims.

2. **Connection files resolve by host.** `provena-mcp`, `provena-agent-context`, and `provena-agent-capture` accept `--host HOST`. It resolves to the ADR 0021 connection file, `${XDG_CONFIG_HOME:-~/.config}/provena/HOST.json`. An explicit `--config` path keeps priority. The plugin therefore references no credential and no user-specific path.

3. **Credentials still come from Provena's own onboarding.** `provena quickstart claude --plugin` and `provena connect claude --plugin` create or refresh the protected connection file, and run the existing service steps, but skip the user-scoped MCP and hook merge. The plugin does not use `userConfig` for the agent key, so credential storage stays in one place.

4. **Never capture a turn twice.** When the `--plugin` mode is selected, the installer removes Provena-owned hooks and the `provena` MCP entry that ADR 0021 previously merged into the user configuration, preserving everything else. `provena status` reports a duplicate if both are present.

5. **Enabling the plugin is the explicit opt-in for capture,** in the same way that running quickstart is today. If the connection file does not exist, the hooks exit successfully without capturing and print one line explaining how to finish setup. This follows the existing fail-open hook behavior.

6. **Versions move together.** The plugin's `version` matches the package version and is included in `scripts/check_release.py`, so `/plugin update` notices each release. CI runs `claude plugin validate --strict` when the Claude Code CLI is available.

## Consequences

- Claude Code users can find and install Provena from a marketplace, and Provena can be listed in plugin directories.
- Python installation and service startup remain separate steps. The plugin README and the hook's setup message must make that obvious.
- The installer gains a removal path for its own previously merged entries. It must remove only entries it can identify as Provena-owned.
- Hook commands are resolved on `PATH`. Users who installed with pipx already have them there.

## Alternatives considered

- **Bundle a Python environment in the plugin.** Rejected because it would duplicate package management, make updates harder, and still not start PostgreSQL.
- **Store the agent key through plugin `userConfig`.** Rejected for now because it splits credential storage from the protected connection file used by every other host.
- **Plugin at the repository root.** Rejected because it would make the whole repository the plugin and mix the plugin's files with the service source.
