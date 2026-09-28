<p align="center">
  <img src="https://raw.githubusercontent.com/admiralpunk/Provena/master/frontend/public/logo.svg" width="96" height="96" alt="Provena logo">
</p>

<!-- mcp-name: io.github.admiralpunk/provena-memory -->

<h1 align="center">Provena</h1>

<p align="center"><strong>Evidence-backed memory for AI agents.</strong><br>Know what an agent remembers—and why.</p>

Provena gives Codex, Claude Code, Gemini CLI, and other MCP clients persistent memory with a traceable source. It stores what was said separately from what an agent inferred, so a remembered claim can be explained, reviewed, and scoped instead of becoming an opaque vector match.

## Product demo

Watch a walkthrough of setup, cross-session recall, and the operator console:

https://github.com/user-attachments/assets/37fe219c-b678-4c6d-811d-bfdd37552628

## Why it exists

An agent can retrieve a relevant fact that is wrong, stale, or taken from an untrusted source. Provena keeps the original evidence and the derived memory separate:

```text
Event:         Alex says, "Pineapple on pizza is a crime."
Claim:         Alex dislikes pineapple on pizza.
Evidence:      The claim links to Alex's original words.

Later event:   Alex says, "I tried it. I owe pineapple an apology."
Updated claim: Alex likes pineapple on pizza.
```

Provena keeps both statements, so it can explain why Alex's preference changed. Events and evidence are append-only. Claims have review status, optional validity time, and exact tenant and project or branch scope. Model-extracted claims remain candidates; source authority is separate from search relevance and never grants permission to act. `memory_explain` traces a claim back to its source, review history, conflicts, and recorded retrievals.

Provena is one FastAPI service backed by PostgreSQL and pgvector. MCP and host hooks capture turns and retrieve attributed context; Ollama or an optional hosted model extracts candidate facts and embeddings. The Next.js console lets a human inspect and review them. [Architecture details](docs/architecture.md) · [Decisions](docs/adr/)

## Get started

You need Python 3.11+, [pipx](https://pipx.pypa.io/latest/how-to/install-pipx.html), Docker Compose, and one supported agent host. Install the connector and choose your host:

```bash
pipx install provena-agent-memory
provena quickstart codex
```

Use `provena quickstart claude` or `provena quickstart gemini` for those hosts. Quickstart starts the local service, PostgreSQL, Ollama, and the console; creates agent and reviewer credentials; and installs MCP plus automatic capture and retrieval hooks. It prints the console URL. Restart your agent host and review Provena under `/hooks` and `/mcp`.

The first run downloads the default models (about 1.26 GB). The local Ollama image is a [digest-pinned CPU build](docs/adr/0022-cpu-only-ollama-image-for-local-setup.md). Installing the package alone does not record conversations; running quickstart is the opt-in step.

To check that the API and database are running:

```bash
provena status
```

### Connect to an existing service

Ask its operator for an API URL, **agent** API key, and project or branch scope ID. With the connector installed, run:

```bash
export PROVENA_API_URL=https://memory.example.com
export PROVENA_API_KEY=paste-agent-key
export PROVENA_SCOPE_ID=paste-scope-id
provena connect codex --install
```

Replace `codex` with `claude` or `gemini` as needed. For another MCP client, use `provena connect generic` to print its configuration. See the [connector guide](PYPI.md#manual-connector-configuration) for manual MCP setup and console access.

### Other setup paths

- **Manual self-hosting:** [download the v0.1.13 Compose file](https://github.com/admiralpunk/Provena/releases/download/v0.1.13/compose.yaml) and follow the [deployment guide](deploy/README.md) for the remaining files, credentials, upgrades, and backups.
- **Develop from source:** follow the [local development guide](docs/development.md) for Python, Docker, the console, and tests.

## Current limits

Retrieval uses an exact scope; branch inheritance is not implemented. Provena records which claims were delivered to an agent, but cannot prove that a later action was caused by them. [More on current guarantees and limits](docs/architecture.md#limits).

## Contributing

Start with a [good first issue](https://github.com/admiralpunk/Provena/issues?q=is%3Aissue%20state%3Aopen%20label%3A%22good%20first%20issue%22) or read [CONTRIBUTING.md](CONTRIBUTING.md). See [SECURITY.md](SECURITY.md) for private vulnerability reporting and [CHANGELOG.md](CHANGELOG.md) for release history.
