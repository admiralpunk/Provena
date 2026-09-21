<p align="center">
  <img src="https://raw.githubusercontent.com/admiralpunk/Provena/master/frontend/public/logo.svg" width="96" height="96" alt="Provena logo">
</p>

<!-- mcp-name: io.github.admiralpunk/provena-memory -->

<h1 align="center">Provena</h1>

<p align="center">
  <strong>Evidence-backed persistent memory for AI agents.</strong><br>
  Know what an agent remembers, where it came from, and why it was retrieved.
</p>

Provena connects Codex, Claude Code, Gemini CLI, and other MCP clients to a shared memory service. Every structured claim retains evidence pointing to its immutable source event, along with scope, authority, review state, validity time, conflicts, and retrieval history.

## Install the connector

Install the connector into a Python 3.11 or newer environment:

```bash
python -m pip install provena-agent-memory
```

## Get access to a Provena service

### Ask your Provena operator

Ask your Provena operator for these three values:

- the Provena API URL;
- an agent API key; and
- the project or branch scope ID the agent may access.

Then continue to **Connect your agent** below.

### Or host the server and local Ollama yourself

You need Docker Engine with Docker Compose and `curl`. Download the current self-hosted release configuration:

```bash
mkdir provena-server
cd provena-server
curl -LO https://github.com/admiralpunk/Provena/releases/latest/download/compose.yaml
curl -LO https://github.com/admiralpunk/Provena/releases/latest/download/compose.ollama.yaml
curl -Lo .env https://github.com/admiralpunk/Provena/releases/latest/download/default.env.example
```

Replace the placeholder database and bootstrap secrets automatically:

```bash
python - <<'PY'
from pathlib import Path
import secrets

path = Path(".env")
text = path.read_text()
text = text.replace("replace-with-a-random-database-password", secrets.token_urlsafe(32))
text = text.replace("replace-with-a-long-random-bootstrap-token", secrets.token_urlsafe(32))
path.write_text(text)
PY
```

Start PostgreSQL, Provena, Ollama, and the local extraction and embedding models:

```bash
docker compose -f compose.yaml -f compose.ollama.yaml up -d
docker compose -f compose.yaml -f compose.ollama.yaml logs -f ollama-models api
```

The first start downloads the configured Ollama models. Press `Ctrl+C` after the model download finishes and the API reports that it is ready; the containers remain running.

Load the local bootstrap token, initialize a workspace, and select the issued agent credential:

```bash
set -a
. ./.env
set +a
export PROVENA_API_URL="http://127.0.0.1:8000"
eval "$(provena init --format shell)"
export PROVENA_API_KEY="$PROVENA_AGENT_KEY"
```

`provena init` also returns `PROVENA_HUMAN_KEY`. Keep that reviewer credential and `BOOTSTRAP_TOKEN` private. Do not place either one in an agent configuration.

## Connect your agent

The self-hosted steps already set the required values in your shell. If an operator provided them instead, export them now:

```bash
export PROVENA_API_URL="https://memory.example.com"
export PROVENA_API_KEY="paste-agent-key"
export PROVENA_SCOPE_ID="paste-scope-id"
```

Verify the service, credential, and scope:

```bash
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
| `provena init` | Bootstrap a running self-hosted service; requires `BOOTSTRAP_TOKEN`. |

The pip package is the agent connector. The self-hosted path runs PostgreSQL, Provena, and Ollama as separate containers. Operators can find security, backup, development, and architecture documentation in the [GitHub repository](https://github.com/admiralpunk/Provena).

## Why provenance matters

Retrieved context can be relevant while still being stale, speculative, or malicious. Provena keeps relevance separate from source authority and from permission to act. Events and evidence remain append-only, candidate claims remain reviewable, and `memory_explain` traces a belief back to the information that produced it.

Provena is licensed under the [MIT License](https://github.com/admiralpunk/Provena/blob/master/LICENSE).
