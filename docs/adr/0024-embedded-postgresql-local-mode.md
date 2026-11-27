# ADR 0024: Embedded PostgreSQL local mode

- Status: Accepted; implementation blocked on a suitable embedded PostgreSQL package
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

## Package evaluation (2026-11-27)

The decision requires a pinned wheel that bundles PostgreSQL with pgvector, runs without root, and supports the platforms and Python versions the connector supports. None of the candidates met that:

| Package | Finding |
|---|---|
| `pgserver` 0.1.4 | Last release June 2024; no wheels for Python 3.12 or newer. |
| `pgserver-search` 0.1.6 | Bundles pgvector, but wheels stop at Python 3.13 and cover only Linux x86-64 and macOS arm64, so `pipx` on a current distribution (Python 3.14) cannot install it. |
| `pg0-embedded` 0.18.1 (MIT) | Python-independent wheels for macOS, Linux, and Windows. On first start it unpacks PostgreSQL 18.7 (about 91 MB) into `~/.pg0`. pgvector is not bundled; it is fetched at runtime from a third-party extension index. Starting an instance failed on Arch Linux because the bundled `libreadline` is injected into the system shell (`undefined symbol: rl_print_keybinding`). |

The PostgreSQL 18.7 binaries unpacked by `pg0` did run when started directly, with pgvector 0.8.1 built from its official source, and the full Provena test suite passed against them, including every real-PostgreSQL integration test. The approach is viable; the packaging is not.

Implementation waits until one of these holds: a maintained wheel bundles pgvector and supports Python 3.11 to 3.14 on Linux and macOS; or `pg0-embedded` bundles pgvector and fixes the shell library injection. An alternative that would need a separate decision is using a PostgreSQL and pgvector installed through the system package manager (for example Homebrew), started by Provena as a user-owned cluster.
