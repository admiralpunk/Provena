## Summary

<!-- Explain the problem and the focused change that solves it. -->

Fixes #

## What changed

- 

## Verification

<!-- List the exact commands or manual workflows you ran and their results. -->

- [ ] Relevant deterministic tests pass.
- [ ] PostgreSQL integration tests pass when a database invariant changed.
- [ ] `npm run typecheck` and `npm run build` pass when the console changed.
- [ ] Documentation and examples match current behavior.

## Provenance and security review

- [ ] Events, evidence links, and audit actions remain append-only.
- [ ] Every new claim is created with evidence in the same transaction.
- [ ] Tenant-owned reads and relationships remain organization-scoped.
- [ ] Authority remains separate from relevance and permission to act.
- [ ] Memory content remains untrusted data.
- [ ] No credentials, private memory content, or customer data are included.

## Architecture

<!-- Link an ADR when this changes a durable design decision or approved invariant. Write "No architecture change" otherwise. -->

No architecture change.

## Risks and migration notes

<!-- Describe compatibility, rollout, or migration concerns. Write "None" when there are none. -->

None.
