<p align="center">
  <img src="https://raw.githubusercontent.com/admiralpunk/Provena/master/frontend/public/logo.svg" width="96" height="96" alt="Provena logo">
</p>

<h1 align="center">Provena</h1>

<p align="center">
  <strong>Evidence-backed persistent memory for AI agents.</strong><br>
  Know what an agent remembers, where it came from, and why it was retrieved.
</p>

Provena connects Codex, Claude Code, Gemini CLI, and other MCP clients to a shared memory service. Every structured claim retains evidence pointing to its immutable source event, along with scope, authority, review state, validity time, conflicts, and retrieval history.

## Install and connect

Install the connector into a Python 3.11 or newer environment:

```bash
python -m pip install provena-agent-memory
```

Ask your Provena operator for these three values:

- the Provena API URL;
- an agent API key; and
- the project or branch scope ID the agent may access.

Export them and verify access:

```bash
export PROVENA_API_URL="https://memory.example.com"
export PROVENA_API_KEY="paste-agent-key"
export PROVENA_SCOPE_ID="paste-scope-id"

provena doctor
```

Generate the MCP configuration for your client:

```bash
provena connect codex
```

Use `claude`, `gemini`, or `generic` in place of `codex` when needed. The generated configuration points to the `provena-mcp` executable installed by pip, so keep that Python environment available to the agent client.

After adding the printed configuration to the client, restart the client. Provena then exposes MCP tools for attributed retrieval, explicit memory capture, candidate claims, and `memory_explain` provenance traces.

## Command roles

| Command | Purpose |
| --- | --- |
| `provena doctor` | Verify API, database, credential, and scope access. |
| `provena connect CLIENT` | Print MCP configuration for an installed connector. |
| `provena status` | Check service health without authenticating. |
| `provena init` | Operator-only bootstrap of a running service; requires `BOOTSTRAP_TOKEN`. |

The pip package is the agent connector. It does not embed PostgreSQL or start a Provena API. Operators can find server deployment, security, backup, development, and architecture documentation in the [GitHub repository](https://github.com/admiralpunk/Provena).

## Why provenance matters

Retrieved context can be relevant while still being stale, speculative, or malicious. Provena keeps relevance separate from source authority and from permission to act. Events and evidence remain append-only, candidate claims remain reviewable, and `memory_explain` traces a belief back to the information that produced it.

Provena is licensed under the [MIT License](https://github.com/admiralpunk/Provena/blob/master/LICENSE).
