# Provena frontend task tracker

This file tracks work specific to the Provena operator console. Check a task only after its acceptance criteria and relevant verification pass. Cross-cutting backend work should remain linked from `planning/tasks.md` rather than duplicated here.

## Completed — approved console foundation

- [x] **FE-01** Create the Next.js App Router application with TypeScript. Evidence: `frontend/package.json`, `frontend/app/`, and a successful production build.
- [x] **FE-02** Implement the shared application shell, desktop navigation, collapsed tablet rail, and native mobile navigation. Evidence: `frontend/components/shell.tsx`.
- [x] **FE-03** Implement reusable buttons, badges, panels, metrics, filters, progress indicators, and table components. Evidence: `frontend/components/ui.tsx` and `frontend/components/claim-table.tsx`.
- [x] **FE-04** Implement the approved Review Inbox design. Evidence: `frontend/app/review/page.tsx`.
- [x] **FE-05** Implement the approved Memory Explorer design. Evidence: `frontend/app/memories/page.tsx`.
- [x] **FE-06** Implement the approved Claim Explain design. Evidence: `frontend/app/memories/claim/page.tsx`.
- [x] **FE-07** Implement the approved Correction and Supersession design. Evidence: `frontend/app/memories/correct/page.tsx`.
- [x] **FE-08** Implement the approved Conflict Review design. Evidence: `frontend/app/conflicts/page.tsx`.
- [x] **FE-09** Implement the approved Retrieval Explorer design. Evidence: `frontend/app/retrievals/page.tsx`.
- [x] **FE-10** Implement the approved Scope Hierarchy design. Evidence: `frontend/app/scopes/page.tsx`.
- [x] **FE-11** Implement the approved Integrations design. Evidence: `frontend/app/integrations/page.tsx`.
- [x] **FE-12** Apply the approved design tokens, self-hosted fonts, responsive behavior, focus states, and accessible control labels. Evidence: `frontend/app/globals.css` and `frontend/app/layout.tsx`.
- [x] **FE-13** Verify the console through TypeScript checking, a static production build, and rendered desktop, tablet, and mobile comparisons against the approved designs.
- [x] **FE-14** Document the frontend boundary and local startup workflow. Evidence: ADR 0016 and `README.md`.

## Next — populate the console with real records

- [x] **FE-15** Add a server-only, typed Provena API client. It must attach credentials only on the Next.js server, validate response shapes, support request timeouts, and expose no API key through browser code or `NEXT_PUBLIC_` variables. Evidence: `frontend/lib/provena/server.ts`, `frontend/.env.example`, and production build.
- [ ] **FE-16** Define shared frontend view models and deterministic API-to-view-model mappers for claims, evidence, authority, extraction metadata, conflicts, scopes, retrievals, and integrations.
- [x] **FE-17** Add explicit loading, empty, unauthorized, unavailable, and error states for every data-backed screen. Evidence: `frontend/app/loading.tsx`, `DataState`, and route-level API error/empty handling.
- [x] **FE-18** Connect the Memory Explorer to a non-auditing operator claims endpoint with pagination, filters, sorting, totals, and all claim statuses. Browsing the ledger must not create an agent `RetrievalEvent`. Evidence: `GET /operator/claims`, `frontend/app/memories/page.tsx`, and PostgreSQL integration coverage.
- [x] **FE-19** Replace the static claim page with `/memories/[claimId]` and populate it from `GET /claims/{claimId}/explain`. Evidence: `frontend/app/memories/[claimId]/page.tsx`.
- [x] **FE-20** Connect the Review Inbox to a real review-queue endpoint, including candidate counts, evidence authority, extraction confidence, source details, and risk flags. Evidence: `GET /operator/review-queue` and `frontend/app/review/page.tsx`; unavailable security assessments are explicitly identified rather than inferred.
- [x] **FE-21** Connect individual review actions to `POST /claims/{claimId}/status`, require an immutable review reason, refresh affected views, and surface authorization or transition failures. Evidence: `frontend/components/interactions.tsx`, `frontend/app/actions.ts`, and the browser-tested candidate-to-active workflow.
- [ ] **FE-22** Add audited batch review behavior with clear per-claim outcomes and retry handling. Do not emulate an atomic batch in browser code.
- [x] **FE-23** Connect Conflict Review to `GET /conflicts` and `POST /conflicts/{caseId}/review`, including explicit supersession direction and reviewer reason. Evidence: `frontend/app/conflicts/page.tsx` and `frontend/app/actions.ts`.
- [ ] **FE-24** Connect the Correction Workflow to one backend atomic supersession command that preserves the original claim and evidence, creates the corrected claim, records the relationship, updates validity, and appends audit actions in one transaction.
- [ ] **FE-25** Connect Retrieval Explorer to retrieval history, retrieval details, similarity scores, exclusions, policy gates, and an explicit query-simulation endpoint.
- [ ] **FE-26** Connect Scope Hierarchy to real organizations, projects, scopes, policy summaries, agents, counts, and branch-difference data.
- [ ] **FE-27** Connect Integrations to real MCP clients, agents, extractor health, storage health, credential metadata, and recent activity without returning raw keys.
- [ ] **FE-28** Implement the Audit Log screen from append-only memory actions, conflict reviews, retrievals, and credential administration events.
- [ ] **FE-29** Implement the Overview screen from real review, conflict, retrieval, extraction, and system-health aggregates.
- [ ] **FE-30** Implement the Settings screen for supported operator policies and configuration. Every mutation must remain server-authorized and audited.
- [x] **FE-31** Replace the hard-coded organization and scope selector with server-authorized context selection and persistent URL-based scope state. Evidence: `GET /operator/context`, `frontend/components/shell.tsx`, and `?scope=` links.
- [ ] **FE-32** Remove `frontend/lib/demo-data.ts` after every approved screen has a real data source and deterministic empty-state fixtures exist for development and tests.

### Current partial work and blockers

- **FE-16:** Shared response types and the claim mapper exist; dedicated mappers for the remaining projections still need deterministic tests.
- **FE-24:** The read side now uses the selected real claim and evidence. The atomic mutation is blocked because the accepted database invariant makes `valid_from` and `valid_to` immutable, while FE-24 currently requires updating the old validity interval. Resolve this through an ADR before implementation.
- **FE-25–FE-30:** Real data is shown where it is recorded. Similarity scores, exclusion diagnostics, policy records, branch diffs, storage health, full cross-entity audit records, and settings mutations remain unmodeled and are never fabricated by the UI.
- **FE-32:** `frontend/lib/demo-data.ts` has been removed. Deterministic frontend test fixtures and coverage remain before this task can be checked.

## Production identity and security

- [ ] **FE-33** Add production user authentication and server-side sessions. Map the signed-in operator to a Provena human credential without exposing the credential to the browser.
- [ ] **FE-34** Enforce organization, project, and branch authorization when selecting scopes and reading or mutating records.
- [ ] **FE-35** Add CSRF protection and origin validation for browser-triggered mutations.
- [ ] **FE-36** Ensure memory content is always rendered as untrusted text. Never interpret event or claim values as HTML, executable instructions, URLs, or client configuration.
- [ ] **FE-37** Add safe session expiry, logout, credential rotation, and revoked-credential handling.
- [ ] **FE-38** Add an operator-visible permission model so disabled actions explain which server-side role or scope permission is required.

## Quality and operations

- [ ] **FE-39** Add deterministic component and mapper tests for states with meaningful behavior. Avoid snapshot tests that only mirror markup.
- [ ] **FE-40** Add real PostgreSQL integration coverage for the Next.js server boundary and FastAPI operator endpoints, including tenant isolation.
- [ ] **FE-41** Add end-to-end tests for claim review, explanation, conflict resolution, correction, scope switching, and authorization failures.
- [ ] **FE-42** Add automated accessibility checks and complete a keyboard and screen-reader review of every interactive workflow.
- [ ] **FE-43** Add Core Web Vitals and bundle-budget checks. Investigate regressions before accepting increases to route JavaScript, CSS, fonts, or image weight.
- [ ] **FE-44** Add frontend error telemetry and request tracing using OpenTelemetry without recording memory payloads, credentials, or other sensitive content.
- [ ] **FE-45** Add a supported deployment configuration, health check, environment-variable reference, and production runbook.
- [x] **FE-46** Audit every visible console interaction and the Overview layout at desktop and mobile widths. Remove inert controls, connect claim assertion, review, conflict, search, filter, tab, pagination, copy, and navigation workflows, and verify loading, validation, success, and error presentation. Evidence: PostgreSQL-backed Chrome audit across all primary routes, zero browser console errors, zero mobile horizontal overflow, 44 px mobile navigation target, and final desktop/mobile visual review.

## Dependency notes

- The operator read APIs, atomic supersession command, production identity, and scope authorization are backend prerequisites. Track their implementation in `planning/tasks.md` and link them here when task identifiers are assigned.
- ADR 0016 requires the Provena API credential to remain server-side. Any decision to change the authentication boundary requires a new or superseding ADR before implementation.
