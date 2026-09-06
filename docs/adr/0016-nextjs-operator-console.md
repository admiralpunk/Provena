# ADR 0016: Add a lightweight Next.js operator console

- Status: Accepted
- Date: 2026-09-20

## Context

Provena now has approved operator-console designs for memory review, claim explanation, correction, conflict resolution, retrieval inspection, scope management, and integrations. The Python service remains the authority for memory state and invariants. The UI must not duplicate those decisions in browser-only logic or expose organization credentials in a client bundle.

## Decision

Add a single Next.js application in `frontend/` using the App Router and TypeScript. Pages and shared layout components are React Server Components by default. Client components are allowed only for interactions that require browser state. The console uses a small in-repository component system and CSS design tokens derived from the approved Figma files. It does not adopt a general UI framework.

The first visual milestone uses typed demonstration records to reproduce the approved screens while the production identity and administrator API boundary remain unresolved. Connecting mutations to the service requires a server-side authenticated boundary; an organization API key must never be embedded in client JavaScript. The existing FastAPI service and PostgreSQL remain the authoritative system of record.

Fonts are self-hosted through build dependencies, icons are tree-shaken SVG React components, and approved images are not shipped with the application. Routes are independently code split by Next.js.

## Consequences

The console can be developed and deployed independently while remaining in the same repository and product architecture. Shared shell, typography, status, panel, and table components prevent per-screen drift. The explicit demonstration-data boundary must be replaced by authenticated server-side queries before operators can review live tenant data.

No evidence, claim, trust, tenant, scope, or action-authority invariant changes. UI labels and controls do not grant permissions; every future write must still be enforced by the FastAPI and PostgreSQL layers.
