# ADR 0015: Organize the service by responsibility

- Status: Accepted
- Date: 2026-09-20

## Context

The service grew from a Phase 1 prototype into REST, MCP, lifecycle hooks, model providers, and pgvector retrieval. All modules still lived in one flat package, so unrelated code appeared equally coupled and generic names such as `models.py` did not reveal whether they represented API contracts, domain types, or database rows. The HTTP module also contained configuration, request schemas, policies, and route wiring.

## Decision

Keep Provena as one deployable service and divide its Python package by responsibility:

- `core` contains dependency-light domain enums and transition rules.
- `persistence` contains SQLAlchemy rows and database metadata.
- `memory` contains fact extraction and embedding provider interfaces and implementations.
- `integrations` contains MCP, host lifecycle hooks, and conversation capture.
- `web` contains FastAPI request schemas, HTTP policies, and application wiring.
- `config.py` contains process configuration.

The repository stores the contents of the logical `provena` package directly under `src/`. Setuptools maps the installed `provena` namespace to that directory explicitly. This avoids a redundant `src/provena/` level while retaining meaningful public imports such as `provena.api` and `provena.integrations`.

`provena.api:app` remains the stable ASGI entry point and re-exports the application factory and settings. Console command names also remain stable while their implementations point to `integrations`.

Imports should point to the owning package rather than through compatibility aliases. Alembic imports metadata from `persistence`. Tests use the same canonical module paths as production code.

## Consequences

The source tree communicates ownership without creating separate services or repositories. Configuration, transport validation, persistence, and agent adapters can change independently while continuing to share one PostgreSQL transaction boundary.

Moving modules changes internal Python import paths and requires the explicit package list in `pyproject.toml` to stay synchronized when a package is added. The documented ASGI and console interfaces remain compatible. This is a source organization decision and does not change evidence immutability, tenant isolation, trust, claim state, retrieval, or any database schema invariant.
