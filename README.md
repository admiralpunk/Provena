<p align="center">
  <img src="https://raw.githubusercontent.com/admiralpunk/Provena/master/frontend/public/logo.svg" width="96" height="96" alt="Provena logo">
</p>

<!-- mcp-name: io.github.admiralpunk/provena-memory -->

<h1 align="center">Provena</h1>

<p align="center"><strong>Agent memory with receipts.</strong><br>Every fact your agent remembers links back to who said it, when, and whether a human approved it.</p>

[![CI](https://github.com/admiralpunk/Provena/actions/workflows/ci.yml/badge.svg?branch=master)](https://github.com/admiralpunk/Provena/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/provena-agent-memory)](https://pypi.org/project/provena-agent-memory/)
[![M8ven Score](https://m8ven.ai/badge/mcp/admiralpunk/provena)](https://m8ven.ai/mcp/admiralpunk/provena)

Provena is open-source, self-hosted memory for AI coding agents. It plugs into **Claude Code, Codex, and Gemini CLI** (and any MCP client), captures your conversations, and brings relevant context into later sessions. Unlike a plain memory store, it keeps the receipts: each remembered claim stays linked to the original words it came from, how much that source can be trusted, and its review history.

<p align="center">
  <img src="docs/assets/provena-console.gif" width="800" alt="Provena console: a candidate claim waits for review, its explain view traces it to the original conversation, and a later session retrieves it">
</p>

```bash
pipx install provena-agent-memory
provena quickstart claude   # or: codex, gemini
```

## Why receipts matter

Agents remember things that are wrong, stale, or planted. A webpage can claim "the user wants every PR auto-merged," and the agent may repeat it in an answer. In a memory store that doesn't track sources, that becomes a fact, and the next session acts on it.

In Provena:

- **Original evidence is never rewritten.** Every conversation turn is stored as an append-only event. Claims are derived from events and always link back to them.
- **Not every source counts the same.** Claims extracted from agent-reported text are low-authority **candidates**. The agent can see them as provisional context, but only a human reviewer can promote one. An agent key cannot.
- **Memory is not permission.** Authority, search relevance, and permission to act are separate. A remembered fact never authorizes an action.
- **Changes of mind keep history.** When a fact changes, both versions stay, and a reviewed relationship records which one supersedes the other.
- **You can ask why.** `memory_explain` traces any claim to its source event, extraction run, review actions, conflicts, and every time it was delivered to an agent.

An example `memory_explain` trail, abridged:

```text
claim       "User is on leave from Dec 1 to Dec 21"
predicate   leave_of_absence  status=candidate  valid 2026-12-01 → 2026-12-21
evidence    user_statement event, Codex session (authority: low)
            "I'll be on leave from December 1st to December 21st."
extraction  qwen2.5:1.5b via Ollama, run recorded
review      awaiting human review
retrievals  delivered to Codex 5 days later for "plan a review meeting in December"
```

## How it compares

Different memory tools make different trade-offs. Provena focuses on provenance and review rather than on minimal setup.

| | Provena | [claude-mem](https://github.com/thedotmack/claude-mem) | [Mem0](https://github.com/mem0ai/mem0) | [Basic Memory](https://github.com/basicmachines-co/basic-memory) | [Hindsight](https://github.com/vectorize-io/hindsight) |
|---|---|---|---|---|---|
| Storage | PostgreSQL + pgvector, self-hosted | SQLite + Chroma, local | Hosted platform or self-hosted SDK | Markdown files + SQLite index | PostgreSQL + pgvector |
| Capture | Automatic hooks (Claude Code, Codex, Gemini CLI) + MCP tools | Automatic Claude Code hooks | MCP tool calls | Agent writes notes | MCP tool calls |
| Focus | Source evidence, authority, human review, audit | Effortless automatic recall | Managed memory platform | Human-readable notes in git | Retrieval quality |
| License | MIT | Apache-2.0 | Apache-2.0 | AGPL-3.0 | MIT |

Pick Provena when you need to know *why* your agent believes something, or when bad memory would be costly. If you only want the lightest possible recall, a local-file tool may suit you better.

## Product demo

Watch the full 90-second walkthrough of setup, cross-session recall, and the operator console:

https://github.com/user-attachments/assets/37fe219c-b678-4c6d-811d-bfdd37552628

Provena is one FastAPI service backed by PostgreSQL and pgvector. MCP and host hooks capture turns and retrieve attributed context. Ollama, or an optional hosted model, extracts candidate facts and embeddings. The Next.js console lets a human inspect and review them. [Architecture details](docs/architecture.md) · [Decisions](docs/adr/)

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

- **Manual self-hosting:** [download the v0.1.15 Compose file](https://github.com/admiralpunk/Provena/releases/download/v0.1.15/compose.yaml) and follow the [deployment guide](deploy/README.md) for the remaining files, credentials, upgrades, and backups.
- **Develop from source:** follow the [local development guide](docs/development.md) for Python, Docker, the console, and tests.

## FAQ

**Do I need Docker?** Yes, for now. Quickstart runs PostgreSQL, Ollama, and the console in Docker Compose. A lighter install is being explored.

**Does it send my conversations anywhere?** No. By default everything runs on your machine, and extraction uses local Ollama models. A hosted model is opt-in.

**How big is the download?** The default local models total about 1.26 GB, downloaded on first run. Extraction runs on CPU.

**Does installing the package start recording?** No. Capture starts only after you run `provena quickstart` or `provena connect --install` for a host.

**Which agents work?** Claude Code, Codex, and Gemini CLI have one-command setup with automatic capture. Other MCP clients can use `provena connect generic` and call the MCP tools directly.

## Current limits

Retrieval uses an exact scope; branch inheritance is not implemented. Provena records which claims were delivered to an agent, but cannot prove that a later action was caused by them. [More on current guarantees and limits](docs/architecture.md#limits).

## Contributing

Start with a [good first issue](https://github.com/admiralpunk/Provena/issues?q=is%3Aissue%20state%3Aopen%20label%3A%22good%20first%20issue%22) or read [CONTRIBUTING.md](CONTRIBUTING.md). See [SECURITY.md](SECURITY.md) for private vulnerability reporting and [CHANGELOG.md](CHANGELOG.md) for release history.
