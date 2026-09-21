# Phase 1 architecture

One FastAPI process writes to PostgreSQL. An event is an immutable source observation. A claim is a structured proposition. Immutable evidence links join claims to events. Claim proposition fields never change; state changes append a MemoryAction in the same transaction.

## Code organization

The code remains one deployable Python service. Its logical `provena` package is stored directly in `src/`: `core` owns domain types and transition rules, `persistence` owns SQLAlchemy mappings, `memory` owns extraction and embedding providers, `integrations` owns MCP and host hooks, and `web` owns HTTP schemas, policies, and application wiring. Setuptools maps `provena` to `src/`, so the stable deployment entry point remains `provena.api:app`. Process settings live in `config.py`; see ADR 0015 for the dependency boundary.

Containment scopes are organization, project, and branch. Agent, task, and session identify context rather than ancestors. Retrieval requires an exact scope ID. Broader visibility requires an explicit future promotion operation.

The API accepts tenant-reported user statements, assistant inferences, and hypotheses. A tenant key cannot prove who originally spoke, so tenant-reported user statements and assistant inferences have low authority. Hypotheses are ephemeral. Medium or high authority requires a future authenticated human or trusted integration identity. Tool observations and test output require a trusted integration identity, which Phase 1 does not issue. The server computes source authority; clients cannot submit a score. Memory authority never grants action authority.

Recorded timestamps are assigned by PostgreSQL. Fact-validity intervals are supplied separately and may be unknown. Different values at the same predicate and scope are returned as possible conflicts when intervals overlap; no automatic supersession occurs.

Exact duplicate and possible-conflict findings are recorded as actions. Possible conflicts also receive a `related_to` relationship marked for review; this is not a confirmed contradiction.

Raw event JSON is stored in PostgreSQL with an API size limit. Binary artifacts and S3-compatible storage are deferred pending a consistent two-store write protocol. Retrieval supports exact filters and pgvector similarity within an exact tenant and scope. Retrieval history proves delivery of a claim, not influence on an action.

Model-derived embeddings live in append-only records separate from claims and evidence. OpenTelemetry instrumentation, SDKs, and a review UI remain deferred.

## Phase 2 agent integration

Agent, human, and tool credentials are stored per organization. The original tenant key migrates to an agent credential. New events store the asserting credential ID, and PostgreSQL checks the role/source/authority combination. Human review credentials alone can change claim states, create reviewed relationships, or resolve possible conflicts. Rotation revokes the old credential while preserving its historical attribution. Local bootstrap is the trust anchor for issuing roles; shared deployment needs an identity provider and delegated administration design.

The local stdio MCP adapter uses an agent credential and a fixed scope. It exposes search, low-authority event recording, candidate proposal, and explain. A deterministic client example runs the protocol without an LLM. MCP itself cannot passively capture chat or tool output; a host must send the source material. Retrieval now returns source summaries with authority so agents can attribute remembered claims.

An atomic `POST /memories` records a text event and optional candidate proposition in one transaction. The MCP `memory_remember` tool uses it for explicit requests and returns both IDs. Portable hooks capture user prompts and final assistant messages from Codex, Claude Code, and Gemini CLI, then request automatic structured extraction. External conversations resolve to idempotent Provena sessions for provenance; retrieval visibility remains controlled by exact scope. Every extracted claim remains linked to the immutable event and carries candidate status. Agent-key submissions of user turns remain low authority and attributable to the agent credential, not to an authenticated human.

Candidate claims are usable as provisional context before review. Retrieval exposes status and source authority, audits the semantic query, and excludes quarantined, expired, superseded, and deleted states. Human review can promote, quarantine, or mark a candidate deleted without erasing its evidence. Local Ollama models perform extraction and embeddings by default; tests substitute a deterministic provider.

Possible conflicts are `related_to` cases until a human records a reviewed decision. The decisions are contradiction, temporal change, or dismissed. Confirmed contradiction adds `contradicts`; temporal change requires the reviewer to choose the superseding claim explicitly before adding `supersedes`. Neither decision silently changes claim status. Original evidence and the case relationship remain.

## Limits

The system does not perform semantic duplicate resolution, automatic temporal resolution, branch inheritance, action-use tracking, or production identity management. The local bootstrap endpoint must be disabled or protected at the deployment edge in any shared environment. Agent credentials attest to the caller's account, not to the identity of a user quoted in an event. REST credentials are organization-wide; project-level access control is future work. The MCP adapter fixes one scope and rejects explanation results outside it, but that local boundary is not a replacement for server-enforced project authorization.

`MemoryAction` records status transitions and duplicate/conflict decisions. `ClaimRelationship` records typed links with a reason. An exact-value duplicate is not merged automatically. A possible conflict is recorded as `related_to`, pending human review. A `supersedes` relationship alone does not change either claim's status.

## Phase 1 completion check

A fresh migration, manual event and claim creation, exact-scope retrieval, and explain tracing all work. Tests against real PostgreSQL cover immutable source material, claim evidence, tenant and branch isolation, status version history, supersession, authority mapping, and non-overlapping temporal facts. Remaining limits above are deliberate Phase 2 work.
