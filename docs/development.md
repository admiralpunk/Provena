# Develop Provena locally

Use this guide when changing the API, memory model, integrations, or operator console. For a packaged installation, use the [quickstart](../README.md#get-started). For deployment from prebuilt images, see the [self-hosting guide](../deploy/README.md).

## Prerequisites

- Python 3.12 or newer
- Node.js 20 or newer and npm
- Docker Engine with Docker Compose

```bash
git clone https://github.com/admiralpunk/Provena.git
cd Provena
python3 -m venv .venv
.venv/bin/pip install -e '.[server,test]'
cp .env.example .env
```

Generate a private bootstrap token with `python3 -c 'import secrets; print(secrets.token_urlsafe(32))'` and replace `BOOTSTRAP_TOKEN` in `.env` with the result. Keep `.env` out of Git.

## Run the API and console

Start PostgreSQL and Ollama, then download the default extraction and embedding models:

```bash
docker compose up -d postgres ollama
docker compose exec ollama ollama pull qwen2.5:1.5b
docker compose exec ollama ollama pull nomic-embed-text
```

Load the environment, migrate the database, and start the API:

```bash
set -a
source .env
set +a
.venv/bin/alembic upgrade head
.venv/bin/uvicorn provena.api:app --reload --host 127.0.0.1 --port 8000
```

In a second Bash terminal, load `.env` again and bootstrap an organization, project scope, agent key, and human reviewer key:

```bash
set -a
source .env
set +a
eval "$(.venv/bin/provena init --format shell)"
```

The keys are returned once. Use the human key for the console and the agent key for MCP or host hooks. Create the console configuration and start Next.js:

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

Open `http://127.0.0.1:3000/overview?scope=YOUR_SCOPE_ID`. The API docs are at `http://127.0.0.1:8000/docs`.

## Run the source stack with Docker

From the repository root, set a private `BOOTSTRAP_TOKEN` in `.env`, then run:

```bash
docker compose up --build -d
docker compose logs -f ollama-models api
```

The model-pull container exits successfully once both models are available. Press `Ctrl+C` to stop following logs; the services keep running. Bootstrap the workspace:

```bash
eval "$(docker compose exec -T api python scripts/bootstrap_workspace.py --format shell)"
PROVENA_API_KEY="$PROVENA_HUMAN_KEY" \
PROVENA_SCOPE_ID="$PROVENA_SCOPE_ID" \
docker compose --profile console up --build -d console
```

The API is at `http://127.0.0.1:8000/docs`; the console is at `http://127.0.0.1:3000/overview?scope=YOUR_SCOPE_ID`. `docker compose --profile console stop` stops the stack without deleting its named PostgreSQL and Ollama volumes.

If upgrading from an older Compose file that did not use a named PostgreSQL volume, back up its database before replacing the containers:

```bash
docker compose exec -T postgres pg_dump -U provena -Fc provena > provena-before-volume.dump
docker compose down
docker compose up -d postgres
until docker compose exec -T postgres pg_isready -U provena -d provena; do sleep 1; done
docker compose exec -T postgres pg_restore -U provena --clean --if-exists --no-owner -d provena < provena-before-volume.dump
```

## Configuration

The tracked [.env.example](../.env.example) documents local defaults. The main settings are:

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | PostgreSQL connection for the API and Alembic. |
| `BOOTSTRAP_TOKEN` | Private token for creating organizations and reviewer credentials. |
| `MEMORY_PROVIDER` | `ollama` by default; `openai` and `none` are also supported. |
| `OLLAMA_BASE_URL` | Local Ollama HTTP endpoint; Compose uses its internal service address. |
| `EXTRACTION_MODEL`, `EMBEDDING_MODEL` | Default to `qwen2.5:1.5b` and `nomic-embed-text`. |
| `PROVENA_API_URL`, `PROVENA_API_KEY`, `PROVENA_SCOPE_ID` | Exact connection used by MCP, host hooks, or the console. |

Do not put a human reviewer key in an agent configuration. Changing the embedding model does not automatically regenerate embeddings for existing claims.

## Tests and release checks

From the repository root, start PostgreSQL and create a disposable integration-test database:

```bash
docker compose up -d postgres
docker compose exec -T postgres sh -c 'createdb -U provena provena_test 2>/dev/null || true'
DATABASE_URL=postgresql+psycopg://provena:provena_dev@127.0.0.1:5437/provena_test \
  .venv/bin/alembic upgrade head
TEST_DATABASE_URL=postgresql+psycopg://provena:provena_dev@127.0.0.1:5437/provena_test \
  .venv/bin/pytest -q
```

Then check migrations and the frontend build:

```bash
DATABASE_URL=postgresql+psycopg://provena:provena_dev@127.0.0.1:5437/provena_test \
  .venv/bin/alembic check
cd frontend
npm run typecheck
npm run build
```

Model-dependent tests stay separate from deterministic tests. Read the [architecture guide](architecture.md) and [ADRs](adr/) before changing memory guarantees or trust boundaries.
