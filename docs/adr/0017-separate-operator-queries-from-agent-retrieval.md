# ADR 0017: Separate operator queries from agent retrieval

- Status: Accepted
- Date: 2026-09-20

## Context

The agent-facing `GET /claims` endpoint is part of Provena's memory retrieval path. It deliberately limits results to retrievable states and appends a `RetrievalEvent` showing that claims were supplied for agent context. The operator console must inspect the complete ledger, including superseded, quarantined, expired, ephemeral, and deleted claims. Treating an operator page view as agent retrieval would produce false influence history and still leave the console without the filters, counts, evidence authority, and review metadata it needs.

The console also needs tenant context, scope topology, unresolved conflicts, extraction failures, retrieval history, audit actions, and integration metadata. Browser code must not receive an organization API key.

## Decision

Add read-only `/operator/*` endpoints to the existing FastAPI service. These endpoints use the same authenticated credential and organization dependency as the rest of the API, require an explicit scope where applicable, and filter every query by the authenticated organization. Operator reads never create `RetrievalEvent`, `MemoryAction`, or other audit records that imply a claim influenced an agent.

The operator responses are projections over the authoritative PostgreSQL records. They may derive display fields such as an evidence authority summary or deterministic proposition label, but they must expose missing information as unavailable rather than fabricate confidence, similarity, risk, health, or policy decisions. Raw credential material is never returned.

The Next.js application calls these endpoints only from server code. `PROVENA_API_KEY` remains a server-side secret and must never use a `NEXT_PUBLIC_` name or be serialized into a React payload. Browser-triggered mutations cross a Next.js server action or route-handler boundary and remain authorized and audited by FastAPI.

## Consequences

The complete ledger can be inspected without polluting retrieval history. Agent retrieval semantics and operator browsing can evolve independently while PostgreSQL remains the system of record. The service gains explicit read models, but no evidence, trust, scope, claim-state, or tenant invariant changes.

Shared production deployment still requires user identity federation and server-enforced project and branch authorization. Until then, a server-held organization credential is suitable only for local or single-operator environments.
