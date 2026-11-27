# ADR 0026: Docker-free local mode with system PostgreSQL

- Status: Accepted
- Date: 2026-11-27
- Preserves: ADR 0001 (single store) and every database invariant
- Alternative to: ADR 0024 (embedded PostgreSQL), whose implementation is blocked
- Extends: ADR 0019, ADR 0020, and ADR 0025

## Context

Local quickstart needs Docker Engine with Docker Compose. ADR 0024 proposed removing that requirement with a pip-installable embedded PostgreSQL, but its package evaluation found no wheel that bundles pgvector and supports the connector's platforms and Python versions.

Most developers who would run Provena without Docker can already install PostgreSQL and pgvector from their package manager. As of 2026-11-27:

| Platform | Packages | PostgreSQL | pgvector | Notes |
|---|---|---|---|---|
| macOS (Homebrew) | `postgresql@18`, `pgvector` | 18.7 | 0.8.7 | Both keg-only: binaries are not on `PATH`. The `pgvector` formula is built for `postgresql@18` and `@19`, not `@17`. |
| Debian 13 (trixie) | `postgresql-17`, `postgresql-17-pgvector` | 17 | 0.8.0 | Main archive. |
| Ubuntu 24.04 (noble) | `postgresql-16`, `postgresql-16-pgvector` | 16 | 0.6.0 | Universe. Newer versions through the PostgreSQL project's apt repository (PGDG). |
| Arch Linux | `postgresql`, `pgvector` | current | 0.8.7 | `extra` repository. |

Provena needs pgvector 0.5.0 or newer (the migration history creates an HNSW index). Every package above qualifies.

Two facts shape the design. The published wheel contains the API code but not the Alembic migrations; only the Docker image includes them. And a full Unix-socket path under a long state directory can exceed PostgreSQL's 107-byte limit, which was observed while testing ADR 0024.

## Decision (proposed)

1. **Opt-in mode.** `provena quickstart HOST --no-docker` runs PostgreSQL and the API as local processes owned by the user. Docker stays the default.

2. **Find PostgreSQL and pgvector; never install them.** Provena looks for `pg_ctl`, `initdb`, and `postgres` in this order:
   - the directory named by `PROVENA_PG_BINDIR`;
   - `pg_config --bindir` for a `pg_config` on `PATH`;
   - Homebrew `$(brew --prefix postgresql@18)/bin`, then `@19`;
   - Debian and Ubuntu `/usr/lib/postgresql/<major>/bin`, newest major first;
   - `PATH`.

   It requires PostgreSQL 16 or newer, and `vector.control` in that installation's `pg_config --sharedir`/extension directory. If either is missing, it stops before changing anything and prints the exact install command for the detected platform (for example `brew install postgresql@18 pgvector`). Provena never runs a package manager or `sudo`.

3. **A private, user-owned cluster.** The data directory is `<state dir>/postgres`, created with `initdb` using SCRAM authentication and a random password stored in the protected state `.env`, never `trust`. The server listens on `127.0.0.1` only, on a free port recorded in the state file, with Unix sockets disabled (`unix_socket_directories = ''`). The cluster never touches a system-wide PostgreSQL service or data directory.

4. **Lock the major version.** The cluster's PostgreSQL major version is recorded at `initdb`. If a later package upgrade changes the major version, Provena refuses to start that cluster and explains the documented `pg_dump` and restore path. It never runs `pg_upgrade` automatically.

5. **Ship migrations in the wheel.** The package includes the Alembic migrations and configuration. The `server` extra provides the API's dependencies (`pipx install 'provena-agent-memory[server]'`). The API process applies migrations at start, as the container does.

6. **Supervise only what Provena started.** `provena start`, `provena stop`, and `provena status` manage the PostgreSQL and API processes through pid files and logs under the state directory. Processes do not survive a reboot unless the user runs `provena start`; installing a login service is out of scope.

7. **Models follow ADR 0025.** `--no-docker` works with an Ollama already running on the machine or with `--no-local-models`. It does not start an Ollama container.

8. **The console is not included at first.** The Next.js console needs Node.js. In this mode review works through the API, and `provena status` says how to start the console with Docker when it is available. A Docker-free console is a separate decision.

9. **Same gate as Docker.** CI runs the real-PostgreSQL integration suite against distribution packages: Ubuntu's PostgreSQL 16 with pgvector 0.6.0, plus PostgreSQL 17 and 18. A version enters the supported range only when that job passes.

## Consequences

- People without Docker can run Provena with one package-manager command plus quickstart, and keep their data in a normal PostgreSQL cluster they can inspect, back up, and remove.
- The single PostgreSQL store, tenant constraints, triggers, and append-only evidence rules do not change.
- Provena takes on process supervision, port selection, logs, and version checks for this mode. These need deterministic tests and clear `provena status` output.
- Distribution packages differ in PostgreSQL and pgvector versions; the CI matrix is the evidence for each supported combination.
- Without the console, human review is less convenient in this mode until a Docker-free console exists.
- Packaging the migrations makes the wheel larger by a few kilobytes and requires a release.

## Alternatives considered

- **Embedded PostgreSQL wheel (ADR 0024).** Preferred if a package ever meets its requirements, because it needs no package manager. Blocked today.
- **SQLite.** Rejected: it would break ADR 0001 and the PostgreSQL-enforced invariants.
- **Running the system PostgreSQL service.** Rejected: it needs administrator rights, shares a server with other applications, and the server's authentication configuration is outside Provena's control. A private user-owned cluster avoids all three.
- **Installing packages automatically.** Rejected: running `brew`, `apt`, or `sudo` on the user's behalf is an outward change Provena should not make silently.

## Open questions

- Whether `provena start` should run automatically from the capture hook when the API is down, or only report it.
- Whether to support Fedora and Windows in the first version, and with which packages.

## Implementation notes

- `provena.local_server` implements discovery, the cluster, and supervision. `PROVENA_PG_BINDIR` is checked first; the chosen directory is recorded in the state file so restarts use the same server.
- pgvector is checked twice: for `vector.control` before anything is created, and in the running server through `pg_available_extensions`.
- The cluster uses `initdb --auth=scram-sha-256` with a password file that is deleted immediately, and starts with `listen_addresses=127.0.0.1` and `unix_socket_directories=''` on a free port. The data directory is mode 0700 and the state file 0600. `PG_VERSION` in the data directory is the major-version lock.
- The API runs as `python -m uvicorn provena.api:app --host 127.0.0.1 --port 8000` with the connector's own interpreter. Stale `DATABASE_URL`, model, and API-key variables from the shell are removed from its environment. Its memory settings are stored in the state file so `provena start` restores them.
- Migrations ship in the wheel as `provena.migrations`, mapped from `alembic/` by setuptools, so the container and development layouts do not change. In an editable install they are found in the repository's `alembic/` directory.
- The Docker-free state directory defaults to `provena-local` beside the Docker state directory. Quickstart refuses to use a Docker state directory for this mode.
- In this mode a host Ollama is reached directly at `127.0.0.1:11434`; without one, recall uses the ADR 0025 full-text fallback.
- Tested end to end with PostgreSQL 18.7 and pgvector 0.8.1: quickstart, plugin capture and recall hooks, stop, restart with data intact, and the full test suite against the Provena-started cluster. CI adds PostgreSQL 16, 17, and 18 from the PostgreSQL apt repository.
