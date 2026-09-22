# Changelog

All notable user-facing changes are recorded here. Provena follows semantic versioning while its public interfaces are in active development.

## [Unreleased]

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

[Unreleased]: https://github.com/admiralpunk/Provena/compare/v0.1.7...HEAD
[0.1.7]: https://github.com/admiralpunk/Provena/compare/v0.1.6...v0.1.7
[0.1.6]: https://github.com/admiralpunk/Provena/compare/v0.1.5...v0.1.6
[0.1.5]: https://github.com/admiralpunk/Provena/compare/v0.1.4...v0.1.5
[0.1.4]: https://github.com/admiralpunk/Provena/compare/v0.1.3...v0.1.4
[0.1.3]: https://github.com/admiralpunk/Provena/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/admiralpunk/Provena/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/admiralpunk/Provena/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/admiralpunk/Provena/releases/tag/v0.1.0
