# ADR 0024: Embedded PostgreSQL local mode

- Status: Proposed
- Date: 2026-11-27
- Preserves: ADR 0001 (single store)
- Extends: ADR 0019 and ADR 0020

## Context

Local quickstart requires Docker Engine with Docker Compose to run PostgreSQL with pgvector, the API, Ollama, and the console. Many people evaluating agent memory tools have no Docker or don't want a container stack for a personal tool. On macOS, Docker Desktop is also a large extra install. Comparable tools install with a single package command and no container runtime.

ADR 0001 makes PostgreSQL the single system of record. AGENTS.md requires tenant boundaries to be database invariants and important invariants to be tested against real PostgreSQL. Replacing PostgreSQL with SQLite would break both.

Python wheels exist that bundle a PostgreSQL server with the pgvector extension and need no root privileges (for example `pgserver` and its forks). They run a real PostgreSQL process from a user data directory.

## Decision (proposed)

1. Add an opt-in local mode, `provena quickstart HOST --no-docker`, that:
   - starts an embedded PostgreSQL server from a pinned wheel, in a per-user data directory, listening on localhost only;
   - runs the existing Alembic migrations;
   - runs the API as a local background process;
   - keeps every database trigger, constraint, and tenant invariant unchanged.
2. The embedded database is still PostgreSQL. All schema changes go through Alembic, and CI runs the real-PostgreSQL integration suite against both the Docker image and the embedded server on Linux and macOS.
3. Docker remains the default until the embedded mode passes that suite on all supported platforms. After that, a separate decision can choose the default.
4. Backups use `pg_dump` from the bundled binaries. Moving between embedded and Docker modes is a documented dump-and-restore, never an automatic copy.
5. The console is served without Docker in this mode, or documented as an optional extra. That choice is made during implementation.

## Consequences

- Removes the Docker requirement for personal local use while keeping one store and the same invariants.
- Adds a native dependency with platform wheels. The pinned package's maintenance, PostgreSQL version, and pgvector version must be checked on each release.
- Embedded PostgreSQL differs from the container image in build flags and available extensions. The integration suite is the gate.
- Process supervision (start, stop, status, logs) becomes Provena's responsibility in this mode.

## Open questions

- Which embedded package to pin, after checking its maintenance and its PostgreSQL and pgvector versions.
- Whether `provena status` should start a stopped embedded server or only report it.
