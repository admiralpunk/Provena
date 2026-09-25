# Provena task tracker

This repository file tracks completed work and the next milestones. Check a task only after its acceptance criteria and relevant tests pass. If work moves to GitHub Issues or Jira, link to the issue here instead of maintaining two separate status lists.

Frontend-specific work is tracked in `planning/frontend-tasks.md`.

## Phase 1 — foundation

- [x] **P1-01** Set up the Python service, local PostgreSQL environment, and development instructions. Evidence: `pyproject.toml`, `compose.yaml`, `README.md`.
- [x] **P1-02** Add the PostgreSQL schema and Alembic migrations. Evidence: `src/persistence/models.py`, `alembic/versions/`.
- [x] **P1-03** Preserve events and evidence; require evidence for every claim. Evidence: database triggers and integration tests.
- [x] **P1-04** Add claims, status history, relationships, and organization/project/branch scopes. Evidence: models, API, and integration tests.
- [x] **P1-05** Add authenticated REST endpoints and exact-scope retrieval. Evidence: `src/api.py`.
- [x] **P1-06** Add `explain` with source events, actions, relationships, and retrieval history. Evidence: `GET /claims/{id}/explain` and integration tests.
- [x] **P1-07** Document engineering rules and architectural decisions. Evidence: `AGENTS.md`, `docs/architecture.md`, `docs/adr/`.
- [x] **P1-08** Add deterministic tests against real PostgreSQL. Evidence: `tests/`; 24 tests passed after operator-console data integration.
- [x] **P1-09** Add a local API usage walkthrough. Evidence: `README.md`.

## Phase 2 — make memory usable by an AI agent

- [x] **P2-01** Build a local MCP adapter for the REST API. An MCP client can search exact-scope active claims, record a low-authority event, propose a candidate claim, and explain a claim. The adapter has no activation tool. Evidence: `src/integrations/mcp_server.py` and MCP protocol test.
- [x] **P2-02** Add an end-to-end agent example. A documented local example retrieves an attributed claim, uses it as context, proposes a new candidate, and explains it. Evidence: `examples/mcp_agent_flow.py`, README, and a successful real stdio smoke run.
- [x] **P2-03** Define human review and promotion rules. Status changes require a human credential, reviewer ID, and reason; agent keys cannot promote claims. Evidence: ADR 0007, ADR 0010, API and PostgreSQL tests.
- [x] **P2-04** Add a trusted identity model. Agent, human, and tool credentials receive authority by role and source; keys can be rotated or revoked; tenant boundaries are tested. Evidence: credential migration, ADR 0007, and integration tests. Local bootstrap remains the trust anchor, not a production identity provider.
- [x] **P2-05** Make conflict review usable. Possible conflicts show both propositions and can be reviewed as contradiction, temporal change with explicit direction, or dismissed, with an immutable decision and reviewer. Evidence: conflict review API, ADR 0008, and integration tests.

## Later — start only when a workflow needs each capability

- [x] **P3-10** Add atomic explicit remember and opt-in host conversation capture. Evidence: `POST /memories`, `memory_remember`, `ConversationCapture`, ADR 0011, and PostgreSQL integration tests. Agent-reported user text stays low authority and all claims stay candidates.
- [x] **P3-11** Add automatic Codex user-prompt capture through a fail-open `UserPromptSubmit` hook. Evidence: `provena-codex-capture`, ADR 0011, README configuration, and deterministic hook tests.

- [x] **P3-01** Add pgvector semantic retrieval for the demonstrated cross-session memory workflow. Candidate results retain status, authority, exact scope, and retrieval audit records.
- [x] **P3-12** Add audited automatic fact extraction for immutable user and assistant events, plus Codex capture and retrieval hooks. Evidence: ADR 0012, extraction runs, derived embeddings, and deterministic integration tests.
- [x] **P3-13** Run extraction and embeddings locally through Ollama by default. Support provider-specific vector dimensions, preserve OpenAI as opt-in, and document the local flow. Evidence: ADR 0013, migration `f6c42d8e0a73`, provider tests, and PostgreSQL integration tests.
- [x] **P3-14** Make agent integration model agnostic. Add portable MCP context and capture tools, normalized Codex/Claude/Gemini lifecycle hooks, and durable external session attribution. Evidence: ADR 0014, migration `a7d53e9f1b84`, and deterministic hook/MCP/PostgreSQL tests.
- [x] **P3-15** Organize the Python service into core, persistence, memory, integration, and web boundaries while preserving public entry points. Evidence: ADR 0015 and the complete deterministic and PostgreSQL test suites.
- [x] **P3-16** Implement the approved Provena operator-console designs with shared, responsive, accessible components and a verified production build. Evidence: `frontend/`, ADR 0016, successful type check and static production build, and desktop/tablet/mobile rendered comparisons against the approved frames.
- [x] **P3-17** Populate the operator console from tenant-scoped PostgreSQL records without recording agent retrievals for operator page views. Evidence: ADR 0017, `/operator/*` read endpoints, server-only Next.js API client, PostgreSQL tenant-isolation test, production build, and a rendered smoke test against 24 local claims.
- [x] **P3-18** Prepare the no-cost public distribution path with lightweight install extras, operator CLI diagnostics, release Compose files, synchronized release metadata, CI, GHCR image publishing, PyPI Trusted Publishing, and MCP Registry metadata. Evidence: ADR 0018, `deploy/`, `server.json`, `.github/workflows/`, and `scripts/check_release.py`. External publication remains a reviewed release action.
- [x] **P3-19** Provide managed command installation and one-command Codex onboarding without manual virtual-environment setup. Ensure quickstart's state file overrides stale shell variables and validate the console reviewer credential before startup. Evidence: ADR 0019, `provena quickstart codex`, Compose environment regression tests, reviewer credential tests, wheel smoke test, and the real PostgreSQL integration suite.
- [x] **P3-20** Publish a lightweight product-demo preview in the GitHub and PyPI project descriptions, backed by a repository-hosted web-ready MP4. Evidence: `docs/assets/provena-product-demo.mp4`, its poster image, README links, and release metadata validation.
- [ ] **P3-02** Add a reviewed branch-to-project promotion workflow.
- [ ] **P3-03** Add action-use reporting once an integration can reliably identify which memory influenced an action.
- [ ] **P3-04** Add OpenTelemetry traces for API, MCP, and retrieval activity.
- [ ] **P3-05** Add S3-compatible raw artifact storage when evidence exceeds the JSON payload policy; design atomicity and recovery first.
- [ ] **P3-06** Add a UI and language SDKs when repeated user workflows justify them.
- [ ] **P3-07** Build an adversarial memory benchmark for poisoning, stale facts, corrections, and temporal change.
- [ ] **P3-08** Replace local bootstrap with production identity federation, delegated administration, and secret management before shared deployment.
- [ ] **P3-09** Add server-enforced project and branch access policies for credentials before granting access to users who should see only part of an organization.

## Working rule

Check existing ADRs before starting a task. Record durable decisions in a new ADR, especially changes to trust, scope visibility, evidence preservation, or tenant boundaries. Keep checkboxes aligned with tested behavior.
