# ADR 0003: Tenant keys and exact containment scopes

Status: Accepted

Tenant-owned references include organization ID in composite foreign keys. Scopes form only an organization/project/branch containment tree. Agents and sessions are provenance context. Phase 1 retrieval uses exact scope matching; no implicit inheritance can leak experimental branch facts into a project.

