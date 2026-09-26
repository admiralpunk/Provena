# Contributing to Provena

Read `AGENTS.md` and the accepted decisions in `docs/adr/` before changing the data model or trust boundaries.

## Your first contribution

1. Choose an open [`good first issue`](https://github.com/admiralpunk/Provena/issues?q=is%3Aissue%20state%3Aopen%20label%3A%22good%20first%20issue%22) that matches your skills.
2. Comment on the issue before starting so another contributor does not duplicate the work.
3. Fork the repository and create a branch from `master`.
4. Keep the change within the issue's scope and add the requested verification.
5. Open a pull request that links the issue and explains what changed, why, and how it was tested.

Documentation, tests, accessibility improvements, reproducible bug reports, and focused code changes are welcome. Ask scope questions on the issue. Never post API keys, private memory content, customer data, or suspected vulnerabilities in a public issue.

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

- Link the issue with `Fixes #<number>` when the pull request fully resolves it.
- Preserve immutable evidence and organization boundaries.
- Add an Alembic migration for every schema change.
- Add real PostgreSQL coverage for database invariants.
- Record durable architecture decisions in `docs/adr/`.
- Keep model-dependent tests separate from deterministic tests.
- Explain what changed, why it changed, how it was tested, and any migration risk.
- Follow `CODE_OF_CONDUCT.md` in every project space.
