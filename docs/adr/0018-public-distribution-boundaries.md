# ADR 0018: Distribute one service with lightweight install extras

- Status: Accepted
- Date: 2026-09-21

## Context

Provena needs a public installation path for self-hosted operators and a small MCP connector for agent users. The existing `provena` distribution name is already owned on PyPI by an unrelated project in a similar product category. Installing the current package also pulls database, web, and model-provider dependencies onto machines that only need the stdio MCP adapter.

Splitting the runtime into independent services would add deployment and consistency problems without improving the evidence model. The API, policy layer, and persistence transaction boundary should remain one service.

## Decision

Publish the Python distribution as `provena-agent-memory` while retaining the `provena` import namespace and product name. Treat the distribution name as distinct from the product brand.

Keep one source package and one server process, but separate installation dependencies:

- the default install contains the CLI, portable HTTP hooks, and stdio MCP runtime;
- the `server` extra installs FastAPI, PostgreSQL, migrations, pgvector, and memory providers;
- the `test` extra supplies the complete deterministic and integration-test environment.

Publish the API and operator console as separate OCI images from the same repository. Release Compose files assemble those images with PostgreSQL and optionally Ollama. PostgreSQL remains the authoritative store, and packaging does not introduce another persistence implementation.

The CLI may bootstrap a workspace, test connectivity, and render client configuration. It must not weaken credential roles, infer authority, or write secrets into client configuration without an explicit operator command.

## Consequences

Agent users can run the MCP connector in an isolated tool environment without installing the server stack. Operators can deploy prebuilt images without cloning or compiling the repository. Source, tests, migrations, and releases remain versioned together.

The PyPI distribution name and OCI tags must use the same semantic version. Public publication remains a release action because package versions and registry records are externally visible and effectively immutable. This decision changes distribution only; it does not change evidence immutability, tenant isolation, claim state, trust, scope, or time invariants.
