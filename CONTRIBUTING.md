# Contributing to Provena

Read `AGENTS.md` and the accepted decisions in `docs/adr/` before changing the data model or trust boundaries.

## Development setup

Follow the local setup in `README.md`, then run:

```bash
docker compose up -d postgres
docker compose exec -T postgres sh -c 'createdb -U provena provena_test 2>/dev/null || true'
DATABASE_URL=postgresql+psycopg://provena:provena_dev@127.0.0.1:5437/provena_test .venv/bin/alembic upgrade head
TEST_DATABASE_URL=postgresql+psycopg://provena:provena_dev@127.0.0.1:5437/provena_test .venv/bin/pytest -q
cd frontend && npm ci && npm run typecheck && npm run build
```

## Pull requests

- Preserve immutable evidence and organization boundaries.
- Add an Alembic migration for every schema change.
- Add real PostgreSQL coverage for database invariants.
- Record durable architecture decisions in `docs/adr/`.
- Keep model-dependent tests separate from deterministic tests.
- Explain what changed, why it changed, how it was tested, and any migration risk.
