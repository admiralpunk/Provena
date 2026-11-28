# Changelog

All notable user-facing changes are recorded here. Provena follows semantic versioning while its public interfaces are in active development.

## [Unreleased]

### Added

- `provena why <topic or claim ID>` prints a receipt for matching memories: the source words, authority, extraction, reviews, conflicts, deliveries to agents, and plain trust warnings. It searches through the operator API, so looking something up never records an agent retrieval.
- `provena demo` runs a scripted scenario in a separate demo project: a fact you stated, a rule planted by a web page, what a later session recalls, and a receipt for each.

- A memory-poisoning benchmark (`benchmarks/poisoning/`) with 23 cases and 127 checks: indirect injection through assistant output, instructions smuggled into memory values, scope and tenant isolation, and contradictions of what the user stated. It runs against real PostgreSQL in CI and was mutation-tested.

### Fixed

- The Docker-free state folder and its `logs/` folder are now owner-only (0700), and `api.log` and the Ollama pull log are 0600. They were readable by other users on the machine, as a macOS test showed. Existing installs are corrected the next time Provena starts.
- The Docker-free PostgreSQL cluster runs in UTC, like the container image, so API timestamps no longer carry the machine's local offset.

## [0.1.17] - 2026-11-27

### Fixed

- Publish the API and console container images and the GitHub release that v0.1.16 could not build: the Dockerfile copied the migrations after installing the package that now ships them. CI builds the API image so this cannot recur unnoticed.
- `PROVENA_PG_BINDIR` is now the only PostgreSQL candidate when set, and pgvector is checked only in the installation being used.

## [0.1.16] - 2026-11-27

### Added

- Add a Claude Code plugin and marketplace (`/plugin install provena --marketplace admiralpunk/Provena`) with the MCP server, capture and recall hooks, and `/provena:status` and `/provena:why` skills (ADR 0023).
- Add `--plugin` to `provena quickstart claude` and `provena connect claude`. It writes the protected connection file and removes Provena hooks and the MCP entry that an earlier user-scoped install added, so turns are not captured twice.
- Add `--host HOST` to `provena-mcp`, `provena-agent-context`, and `provena-agent-capture` to read the connection file that onboarding wrote for that host. Hooks stay inert, and exit successfully, until it exists.
- `provena status` warns when the plugin and user-scoped hooks would capture every turn twice.
- Quickstart no longer blocks on the 1.26 GB model download. Models download in the background, an Ollama already running on the machine is reused, and `--no-local-models` runs without models (ADR 0025). `--wait-for-models` keeps the previous behavior.
- Text recall falls back to audited PostgreSQL full-text search (`method = fulltext`) when no model is configured or models are not ready yet.
- Add `provena catch-up` and `POST /scopes/{id}/catch-up` to extract turns captured before models were ready and embed claims that lack embeddings, including claims saved with `memory_remember`, which previously could not be found by semantic search.
- `provena status` reports whether the memory models are ready (`GET /intelligence`).
- Add a Docker-free mode, `provena quickstart HOST --no-docker` (ADR 0026). It finds a PostgreSQL 16+ with pgvector from Homebrew, apt, or pacman (never installing it), creates a private cluster bound to 127.0.0.1 with SCRAM authentication and no Unix socket, applies migrations, and starts the API. `provena start`, `provena stop`, and `provena status` manage it; a changed PostgreSQL major version is refused instead of upgraded.
- Ship the database migrations in the wheel, so the API can migrate without the container image.
- CI runs the full test suite against PostgreSQL 16, 17, and 18 from the PostgreSQL apt repository, on clusters started by Provena's own code.

### Fixed

- Show agents why an MCP tool failed. An unreachable service, rejected credentials, an invalid ID, or an out-of-scope claim now returns a specific message with a next step, instead of the bare `Error executing tool <name>` that the MCP SDK reports for unexpected exceptions.

## [0.1.15] - 2026-09-29

### Fixed

- Keep the MCP Registry description within its 100-character limit and validate that limit before tagging.
- Publish matching package and registry metadata from one release tag.

## [0.1.14] - 2026-09-29

### Changed

- Make the README shorter and move detailed local development and self-hosting steps into focused guides.
- Use a simple change-of-mind example to explain events, claims, and preserved evidence.
- Clarify Provena's self-hosted MCP memory role in the README, PyPI description, and MCP Registry metadata.
- Add package discovery keywords and links to the changelog and security policy.

## [0.1.13] - 2026-09-28

### Changed

- Use a digest-pinned CPU-only Ollama image in local and release Compose setups, reducing the Linux/amd64 image download while keeping the existing extraction and embedding models.
- Document the third-party image choice and CPU-only behavior in the setup guides and ADR 0022.

## [0.1.12] - 2026-09-27

### Changed

- Improve contributor onboarding and project demo links.
- Expand MCP configuration output test coverage.

## [0.1.11] - 2026-09-25

### Changed

- Render the product demo as GitHub's native audio-enabled player while retaining the browser-streaming demo link on PyPI.

### Added

- Add `provena quickstart claude` and `provena quickstart gemini` with automatic user-scoped MCP, conversation capture, and attributed context retrieval.
- Support `provena connect claude --install` and `provena connect gemini --install` for existing Provena services.

## [0.1.10] - 2026-09-25

### Fixed

- Serve the product demo through a browser-streamable `video/mp4` URL from the repository-backed CDN.

## [0.1.9] - 2026-09-25

### Added

- Add a repository-hosted 90-second product demo with a lightweight poster preview to the GitHub and PyPI project descriptions.

## [0.1.8] - 2026-09-23

### Changed

- Make `pipx install provena-agent-memory` the primary installation path so users do not manage or activate a Python environment.

### Fixed

- Prevent stale exported shell variables from overriding the quickstart deployment's image version, console credential, or scope.
- Validate the persisted console reviewer credential and replace it when a reused Codex connection belongs to the current workspace but the reviewer key is missing, invalid, or not a human credential.

## [0.1.7] - 2026-09-23

### Added

- Add `provena quickstart codex` for version-matched local deployment, bootstrap, Codex setup, automatic memory, and console startup.
- Add `provena connect codex --install` for one-command MCP and lifecycle-hook configuration against an existing service.
- Store the agent connection once in a protected file referenced by MCP and hooks.

### Fixed

- Render claim status review in a top-layer modal so fixed navigation and clipped review cards cannot cover the form.
- Preserve unrelated Codex hooks and replace earlier Provena handlers idempotently.

## [0.1.6] - 2026-09-23

### Fixed

- Preserve an existing self-hosted `.env` when refreshing release files.
- Document data-preserving recovery when the API and an existing PostgreSQL volume use different passwords.

## [0.1.5] - 2026-09-22

### Changed

- Document the complete Codex MCP configuration and verification workflow on PyPI.
- Explain how operators start the browser console with a human reviewer credential.

## [0.1.4] - 2026-09-22

### Changed

- Explain how connector users can request operator credentials or self-host Provena with PostgreSQL and local Ollama.
- Publish the deployment environment template under the explicit `default.env.example` asset name.

## [0.1.3] - 2026-09-22

### Fixed

- Include the MCP Registry ownership marker in the PyPI package description.

## [0.1.2] - 2026-09-22

### Changed

- Give PyPI users one pip-installed connector workflow in a dedicated package description.
- Generate MCP client configuration with the installed `provena-mcp` executable instead of a second `uvx` runtime.

## [0.1.1] - 2026-09-22

### Fixed

- Render the Provena logo on PyPI through an absolute HTTPS asset URL.
- Avoid slow ARM64 emulation when publishing the operator console image.
- Run continuous integration for the repository's `master` branch.

## [0.1.0] - 2026-09-21

### Added

- Immutable source events, evidence-backed claims, claim relationships, status history, and exact tenant scopes.
- Explainable retrieval with source authority, provisional candidate claims, conflict review, and retrieval audit records.
- REST, stdio MCP, and model-agnostic conversation lifecycle integrations.
- Local Ollama extraction and embeddings with an optional OpenAI provider.
- PostgreSQL and pgvector persistence with Alembic migrations and database-enforced invariants.
- Next.js operator console for overview, review, conflicts, retrievals, scopes, integrations, audit, and settings.
- Versioned self-hosted Compose deployment and public release automation.

[Unreleased]: https://github.com/admiralpunk/Provena/compare/v0.1.15...HEAD
[0.1.15]: https://github.com/admiralpunk/Provena/compare/v0.1.14...v0.1.15
[0.1.14]: https://github.com/admiralpunk/Provena/compare/v0.1.13...v0.1.14
[0.1.13]: https://github.com/admiralpunk/Provena/compare/v0.1.12...v0.1.13
[0.1.12]: https://github.com/admiralpunk/Provena/compare/v0.1.11...v0.1.12
[0.1.11]: https://github.com/admiralpunk/Provena/compare/v0.1.10...v0.1.11
[0.1.10]: https://github.com/admiralpunk/Provena/compare/v0.1.9...v0.1.10
[0.1.9]: https://github.com/admiralpunk/Provena/compare/v0.1.8...v0.1.9
[0.1.8]: https://github.com/admiralpunk/Provena/compare/v0.1.7...v0.1.8
[0.1.7]: https://github.com/admiralpunk/Provena/compare/v0.1.6...v0.1.7
[0.1.6]: https://github.com/admiralpunk/Provena/compare/v0.1.5...v0.1.6
[0.1.5]: https://github.com/admiralpunk/Provena/compare/v0.1.4...v0.1.5
[0.1.4]: https://github.com/admiralpunk/Provena/compare/v0.1.3...v0.1.4
[0.1.3]: https://github.com/admiralpunk/Provena/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/admiralpunk/Provena/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/admiralpunk/Provena/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/admiralpunk/Provena/releases/tag/v0.1.0
