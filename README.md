<p align="center">
  <img src="https://raw.githubusercontent.com/admiralpunk/Provena/master/frontend/public/logo.svg" width="96" height="96" alt="Provena logo">
</p>

<!-- mcp-name: io.github.admiralpunk/provena-memory -->

<h1 align="center">Provena</h1>

<p align="center">
  <strong>Evidence-backed persistent memory for AI agents.</strong><br>
  Know what an agent remembers, where it came from, and why it was retrieved.
</p>

Provena gives Codex, Claude Code, Gemini CLI, custom agents, and other MCP clients a shared long-term memory layer with explicit provenance. It stores source events separately from structured claims, links every claim to immutable evidence, records review and retrieval history, and keeps source authority separate from semantic relevance.

The result is agent context that can be inspected, challenged, scoped, and explained instead of an opaque collection of vector matches.

## Product Demo

> **Loom walkthrough coming soon.**
>
> Replace this block with a linked Loom thumbnail or embedded preview. The surrounding section is intentionally ready for the final demo asset.

## What is Provena?

Provena is a memory service and integration harness for AI-assisted development workflows. It sits between an agent host and durable storage through REST, MCP, or lifecycle hooks.

The harness is responsible for:

- capturing selected user and assistant turns as immutable source events;
- accepting explicit, structured memories from an agent or application;
- extracting candidate facts with a configured local or hosted model;
- retrieving relevant claims from one exact organization and scope;
- returning source attribution, status, and authority with retrieved context; and
- recording which claims were delivered during each retrieval.

Provena does **not** execute an agent's code or tasks. Its role in the execution context is to make memory capture and context assembly traceable. Retrieval records improve reproducibility by showing which stored claims were supplied to an agent, but Provena does not currently replay a model run or prove that a retrieved claim influenced a later action.

### Core model

| Record | Meaning |
| --- | --- |
| **Event** | Immutable source material, such as a user statement, assistant inference, hypothesis, or tool observation. |
| **Claim** | A structured proposition: subject, predicate, JSON value, validity interval, and review state. |
| **Evidence** | An immutable link from a claim to the event that supports it. |
| **Memory action** | An append-only status transition or review decision with actor, reason, and version. |
| **Claim relationship** | A typed link such as `supports`, `contradicts`, `supersedes`, `derived_from`, or `related_to`. |
| **Retrieval event** | An audit record of a query and the exact claims returned to an agent. |
| **Scope** | An exact organization, project, or branch boundary for stored and retrieved memory. |

Claims can be candidates, active, verified, conflicted, superseded, quarantined, expired, ephemeral, or deleted. Changing state never erases the claim's source evidence.

## Why Provenance Matters

Agent memory can be relevant and still be wrong, stale, speculative, or malicious. A vector result alone cannot answer who asserted a fact, what the original source said, whether a human reviewed it, or which execution context received it.

Provena preserves those distinctions:

- **Traceability:** `memory_explain` follows a claim back to its source event, credential, extraction run, relationships, status history, and recorded retrievals.
- **Verification:** human credentials review state transitions; agent-generated summaries cannot promote themselves into high-authority facts.
- **Auditability:** events, evidence links, relationships, and memory actions are append-only.
- **Temporal clarity:** recorded time and fact-validity time are stored separately.
- **Conflict awareness:** overlapping claims with different values remain visible until a reviewer records a contradiction, temporal change, or dismissal.
- **Isolation:** tenant-owned records include organization IDs, and retrieval requires an exact scope.
- **Security:** remembered content is treated as untrusted data and never grants permission to perform an action.

PostgreSQL is the authoritative system of record. pgvector embeddings are derived indexes; they do not replace evidence or determine authority.

## How Provena Works

```mermaid
flowchart LR
    A[Agent, CLI, or host application] --> B[REST, MCP, or lifecycle hook]
    B --> C[Provena capture and retrieval harness]
    C --> D[FastAPI policy and transaction boundary]
    D --> E[(PostgreSQL + pgvector)]
    C --> F[Ollama or OpenAI\noptional extraction and embeddings]
    E --> G[Attributed context or explain response]
    G --> A
    E --> H[Next.js operator console]
```

A typical write and retrieval flow is:

```text
source turn or explicit memory
  → immutable event
  → candidate claim linked through evidence
  → duplicate and conflict checks
  → optional human review
  → exact-scope semantic retrieval
  → attributed context plus retrieval audit record
```

Model output never raises source authority or activates a claim. Candidate claims may be returned as clearly marked provisional context until a human promotes, quarantines, or deletes them.

## Use Cases

- **Cross-session agent memory:** share reviewed project facts or user constraints across Codex, Claude Code, Gemini CLI, and custom clients using the same organization and scope.
- **Explainable preferences:** preserve a statement such as a dietary restriction and show the exact event behind the structured preference.
- **Architecture memory:** record decisions such as a production database, runtime, or deployment policy with validity time and source evidence.
- **Conflict review:** distinguish a contradiction from a temporal migration or a fact that belongs to another environment.
- **Branch experiments:** isolate feature-branch facts in a branch scope so they do not silently enter project-scope retrieval.
- **Context auditing:** inspect the exact claims delivered in an agent retrieval without treating operator browsing as another agent retrieval.

## Getting Started

### Fastest self-hosted release setup

Published releases provide prebuilt API and console images. Download the three deployment files from the matching GitHub release, then create local configuration:

```bash
mkdir provena && cd provena
curl -LO https://github.com/admiralpunk/Provena/releases/download/v0.1.4/compose.yaml
curl -LO https://github.com/admiralpunk/Provena/releases/download/v0.1.4/compose.ollama.yaml
curl -Lo .env.example https://github.com/admiralpunk/Provena/releases/download/v0.1.4/default.env.example
cp .env.example .env
```

Generate separate values for `POSTGRES_PASSWORD` and `BOOTSTRAP_TOKEN`, place them in `.env`, and start core mode:

```bash
python -c 'import secrets; print(secrets.token_urlsafe(32))'
docker compose up -d postgres api
docker compose exec api provena status --api-url http://127.0.0.1:8000
docker compose exec api provena init --format shell
```

Core mode supports explicit memories and review without downloading a model. To enable local automatic extraction and semantic retrieval, add the Ollama override:

```bash
docker compose -f compose.yaml -f compose.ollama.yaml up -d
```

Save the one-time credentials printed by `provena init`. Add the human key and scope ID to `.env` before starting the optional console profile. See [`deploy/README.md`](deploy/README.md) for upgrades and backups.

### Prerequisites

For local development:

- Python 3.12 or newer
- Node.js 20 or newer and npm
- Docker Engine with Docker Compose, used for PostgreSQL and local Ollama
- `curl`

For the containerized setup, only Docker Engine, Docker Compose, and `curl` are required.

```bash
git clone https://github.com/admiralpunk/Provena.git
cd Provena
```

### Option 1: Run Locally

Install the Python service and its MCP and test dependencies:

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[server,test]'
cp .env.example .env
```

Set a private `BOOTSTRAP_TOKEN` in `.env`, then start PostgreSQL and Ollama and install the default local models:

```bash
docker compose up -d postgres ollama
docker compose exec ollama ollama pull qwen2.5:1.5b
docker compose exec ollama ollama pull nomic-embed-text
```

Migrate the database and start the API:

```bash
set -a
source .env
set +a
.venv/bin/alembic upgrade head
.venv/bin/uvicorn provena.api:app --reload --host 127.0.0.1 --port 8000
```

The API is now available at `http://127.0.0.1:8000`; interactive OpenAPI documentation is at `http://127.0.0.1:8000/docs`. Verify API and database readiness with:

```bash
.venv/bin/provena status
```

In a second Bash terminal, load the same configuration and create a local organization, project scope, agent credential, and human review credential:

```bash
set -a
source .env
set +a
eval "$(.venv/bin/provena init --format shell)"
```

The bootstrap credentials are returned once and exported only in the current shell. Start the operator console with the human credential:

```bash
cat > frontend/.env.local <<EOF
PROVENA_API_URL=http://127.0.0.1:8000
PROVENA_API_KEY=$PROVENA_HUMAN_KEY
PROVENA_SCOPE_ID=$PROVENA_SCOPE_ID
EOF

cd frontend
npm ci
npm run dev
```

Open `http://127.0.0.1:3000/overview?scope=$PROVENA_SCOPE_ID`.

### Option 2: Run with Docker

<details>
<summary>Upgrading from the earlier Compose file without a named PostgreSQL volume?</summary>

Back up the existing database before the first restart with this Compose file, then restore it into the new named volume:

```bash
docker compose exec -T postgres pg_dump -U provena -Fc provena > provena-before-volume.dump
docker compose down
docker compose up -d postgres
until docker compose exec -T postgres pg_isready -U provena -d provena; do sleep 1; done
docker compose exec -T postgres pg_restore -U provena --clean --if-exists --no-owner -d provena < provena-before-volume.dump
```

</details>

Copy the environment template and replace `BOOTSTRAP_TOKEN` with a private value:

```bash
cp .env.example .env
docker compose up --build -d
```

The first start downloads the configured Ollama extraction and embedding models. Follow progress and verify the API:

```bash
docker compose logs -f ollama-models api
curl -fsS http://127.0.0.1:8000/openapi.json > /dev/null && echo "Provena API is ready"
```

Press `Ctrl+C` after the services are ready; the containers continue running in the background.

Create the initial workspace from inside the API container:

```bash
eval "$(docker compose exec -T api python scripts/bootstrap_workspace.py --format shell)"
```

Then start the console profile with the issued human credential and project scope:

```bash
PROVENA_API_KEY="$PROVENA_HUMAN_KEY" \
PROVENA_SCOPE_ID="$PROVENA_SCOPE_ID" \
docker compose --profile console up --build -d console
```

Open:

- API documentation: `http://127.0.0.1:8000/docs`
- Operator console: `http://127.0.0.1:3000/overview?scope=$PROVENA_SCOPE_ID`

Stop the stack without deleting memory:

```bash
docker compose --profile console stop
```

PostgreSQL and Ollama use named volumes. Add `docker compose --profile console down --volumes` only when you intentionally want to destroy the local database and downloaded models.

## Connect an AI Agent

Install the published connector in a persistent Python environment. Generate a configuration using the **agent** credential and one exact scope:

```bash
python3 -m venv ~/.venvs/provena
~/.venvs/provena/bin/pip install provena-agent-memory
export PROVENA_API_URL=http://127.0.0.1:8000
export PROVENA_API_KEY=paste-agent-key
export PROVENA_SCOPE_ID=paste-project-or-branch-scope-id
~/.venvs/provena/bin/provena connect codex
```

Use `claude`, `gemini`, or `generic` instead of `codex` to print the corresponding JSON configuration. The resulting MCP command uses:

```json
{
  "command": "/home/user/.venvs/provena/bin/provena-mcp",
  "env": {
    "PROVENA_API_URL": "http://127.0.0.1:8000",
    "PROVENA_API_KEY": "paste-agent-key",
    "PROVENA_SCOPE_ID": "paste-project-or-branch-scope-id"
  }
}
```

After adding the configuration, verify the same credential and scope independently:

```bash
~/.venvs/provena/bin/provena doctor
```

The MCP adapter exposes:

- `memory_context` and `memory_search` for attributed retrieval;
- `memory_record_event` and `memory_capture_turn` for source capture;
- `memory_remember` and `memory_propose_claim` for evidence-backed candidate claims; and
- `memory_explain` for provenance, review, conflict, and retrieval history.

Agent keys can create events and candidate claims. Only human credentials can review claim status or resolve conflicts. Host sessions provide provenance labels; they do not create separate memory stores. See [ADR 0014](docs/adr/0014-model-agnostic-agent-integration.md) for the model-agnostic integration boundary.

## Configuration

### Service and model settings

| Variable | Default | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | `postgresql+psycopg://provena:provena_dev@localhost:5437/provena` | SQLAlchemy connection for the authoritative PostgreSQL store. |
| `BOOTSTRAP_TOKEN` | empty | Local trust anchor for creating organizations and issuing, rotating, or revoking credentials. Required for bootstrap operations. |
| `MEMORY_PROVIDER` | `ollama` | Memory intelligence provider: `ollama`, `openai`, or `none`. |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Ollama HTTP endpoint. Compose overrides this with the internal service address. |
| `EXTRACTION_MODEL` | `qwen2.5:1.5b` | Fact extraction model. Provider-prefixed model names are stored as provenance. |
| `EMBEDDING_MODEL` | `nomic-embed-text` | Embedding model used for semantic retrieval. |
| `OPENAI_API_KEY` | empty | Required only when `MEMORY_PROVIDER=openai`. |

### Console, MCP, and hook settings

| Variable | Purpose |
| --- | --- |
| `PROVENA_API_URL` | Base URL of the Provena REST API. |
| `PROVENA_API_KEY` | Server-side console or agent credential. Never expose it as a `NEXT_PUBLIC_` variable. |
| `PROVENA_SCOPE_ID` | Exact project or branch scope used for capture and retrieval. |
| `PROVENA_AGENT_HOST` | Optional host label used by portable lifecycle hooks for session provenance. |

Use a human credential for the local console if you need review and conflict actions. Use an agent credential for MCP and automatic capture. Do not give a conversational agent the human review key.

## Development

Start only the development dependencies:

```bash
docker compose up -d postgres ollama
```

Create and migrate the disposable integration-test database, then run the deterministic suite:

```bash
docker compose exec -T postgres sh -c 'createdb -U provena provena_test 2>/dev/null || true'
DATABASE_URL=postgresql+psycopg://provena:provena_dev@127.0.0.1:5437/provena_test \
  .venv/bin/alembic upgrade head
TEST_DATABASE_URL=postgresql+psycopg://provena:provena_dev@127.0.0.1:5437/provena_test \
  .venv/bin/pytest -q
```

Validate migrations and the frontend production build:

```bash
DATABASE_URL=postgresql+psycopg://provena:provena_dev@127.0.0.1:5437/provena_test \
  .venv/bin/alembic check
cd frontend
npm run typecheck
npm run build
```

Model-dependent behavior is isolated behind the memory intelligence interface. Deterministic tests use fake transports and do not require model calls.

## Project Structure

```text
src/
  core/           domain enums and state-transition rules
  persistence/    SQLAlchemy mappings and database invariants
  memory/         extraction and embedding providers
  integrations/   MCP, conversation capture, and host lifecycle hooks
  web/            FastAPI routes, policies, schemas, and operator projections
alembic/           versioned PostgreSQL migrations
frontend/          Next.js operator console
scripts/           local setup helpers
deploy/            versioned self-hosted release Compose files
docs/adr/          durable architecture decisions
examples/          deterministic MCP client flow
tests/             domain and real-PostgreSQL integration tests
compose.yaml       local PostgreSQL, Ollama, API, and optional console stack
server.json        official MCP Registry package metadata
```

Read [the architecture guide](docs/architecture.md) for current guarantees and limits. Accepted decisions live in [`docs/adr/`](docs/adr/).

## Current Limits

Provena currently uses exact-scope retrieval; branch inheritance and cross-scope promotion are not implemented. It records claim delivery but not whether an agent action was caused by that claim. Binary artifact storage, production identity federation, semantic duplicate resolution, automatic temporal resolution, and a general task execution sandbox are outside the current implementation.

Raw event payloads, claims, evidence, actions, extraction metadata, embeddings, and retrieval membership are stored in PostgreSQL. This keeps the provenance transaction atomic while broader artifact storage remains deferred.

## Contributing

Keep changes small and preserve the evidence and tenant-boundary invariants. Use Alembic for schema changes, add real PostgreSQL coverage for database guarantees, and record durable architecture decisions in `docs/adr/`. Run the backend tests, frontend type check, and production build before opening a change.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the contributor workflow, [SECURITY.md](SECURITY.md) for private vulnerability reporting, and [CHANGELOG.md](CHANGELOG.md) for release history.
