# Public release guide

Provena's public distribution uses services that are free for public open-source projects: GitHub Actions, GitHub Container Registry, PyPI Trusted Publishing, and the official MCP Registry.

## One-time repository setup

1. Make the GitHub repository public.
2. In repository settings, keep Actions workflow permissions read-only by default. The release jobs request `packages: write`, `contents: write`, or `id-token: write` only where required.
3. Create a protected GitHub environment named `pypi` and require manual approval.
4. On PyPI, add a pending Trusted Publisher with:
   - project: `provena-agent-memory`
   - owner: `admiralpunk`
   - repository: `Provena
   `
   - workflow: `release.yml`
   - environment: `pypi`
5. After the first image release, set the two GHCR packages to public visibility. Public packages do not require users to authenticate when pulling.

PyPI names are not reserved by source code. Confirm `provena-agent-memory` is still available immediately before the first release.

## Prepare a version

Update the version in:

- `pyproject.toml`
- `frontend/package.json` and `frontend/package-lock.json`
- `server.json`, including its package version
- `deploy/.env.example`
- `CHANGELOG.md`

Then run:

```bash
python scripts/check_release.py
TEST_DATABASE_URL=postgresql+psycopg://provena:provena_dev@127.0.0.1:5437/provena_test .venv/bin/pytest -q
cd frontend && npm run typecheck && npm run build
```

Build the public artifacts locally:

```bash
.venv/bin/pip install -e '.[release]'
.venv/bin/python -m build
.venv/bin/python -m twine check dist/*
docker compose build api console
docker compose --env-file deploy/.env.example -f deploy/compose.yaml config --quiet
```

## Publish

Create the release only from a reviewed commit with green CI:

```bash
VERSION=0.1.8
git tag -a "v${VERSION}" -m "Provena ${VERSION}"
git push origin "v${VERSION}"
```

The tag starts `.github/workflows/release.yml`, which:

1. rejects inconsistent version metadata;
2. builds and checks the wheel and source distribution;
3. waits for approval in the `pypi` environment;
4. publishes to PyPI through short-lived OIDC credentials;
5. publishes AMD64 and ARM64 API images and an AMD64 console image to GHCR;
6. publishes `server.json` to the MCP Registry through GitHub OIDC; and
7. creates a GitHub release with packages and deployment files.

PyPI versions cannot be replaced. If publication is incorrect, fix the issue and release a new version.

## Post-release smoke test

On a clean machine, download only the GitHub release deployment files and verify:

```bash
docker compose pull
docker compose up -d postgres api
docker compose exec api provena status --api-url http://127.0.0.1:8000
uvx --from provena-agent-memory provena-mcp
```

The last command should report the required API key and scope when they are absent, proving that the published MCP entry point loads. Complete a two-session remember, retrieve, and explain workflow before announcing the release.
