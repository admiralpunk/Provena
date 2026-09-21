# Self-hosted release deployment

These Compose files use prebuilt, versioned images. They are intended for evaluating Provena on one machine. Ports bind to loopback by default; place an authenticated TLS reverse proxy in front of the service before exposing it to a network.

## Core mode

Core mode supports explicit memories, manual claims, review, provenance, and full-text retrieval without downloading an extraction model.

```bash
cp .env.example .env
python -c 'import secrets; print(secrets.token_urlsafe(32))'
docker compose pull
docker compose up -d postgres api
docker compose exec api provena status --api-url http://127.0.0.1:8000
docker compose exec api provena init --format shell
```

Use two different generated values for `POSTGRES_PASSWORD` and `BOOTSTRAP_TOKEN` before starting the services. Save the credentials printed by `provena init`; API keys cannot be recovered later.

Add the human key and scope ID to `.env`, then start the console:

```bash
docker compose --profile console up -d console
```

## Local intelligence mode

The optional override adds Ollama and downloads the configured extraction and embedding models:

```bash
docker compose -f compose.yaml -f compose.ollama.yaml up -d postgres ollama ollama-models api
```

## Upgrades and backups

Pin `PROVENA_VERSION` in `.env`. Before changing it, create a PostgreSQL backup:

```bash
docker compose exec -T postgres pg_dump -U provena -Fc provena > provena.dump
docker compose pull
docker compose up -d
```

Stopping the stack preserves the named PostgreSQL volume:

```bash
docker compose --profile console stop
```

Do not use `down --volumes` unless you intend to destroy the local memory database.
