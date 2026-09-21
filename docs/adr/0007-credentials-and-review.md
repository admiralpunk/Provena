# ADR 0007: Credentials carry source capabilities; humans review memory state

Status: Accepted

Phase 1 used one tenant key. That key cannot establish who originally spoke or whether a tool produced a result. Phase 2 introduces organization-scoped credentials with fixed roles: `agent`, `human`, and `tool`. The existing tenant key migrates to an agent credential. The local bootstrap secret may issue role-specific credentials and rotate or revoke them. This is a local trust anchor, not a production identity provider.

Event authority is assigned from both the authenticated credential role and source kind. Agents may submit user-reported text only as low authority; human credentials may submit user statements and corrections; tool credentials may submit observations and test output. Events retain the credential ID and assigned authority after rotation or revocation. Client-supplied `actor_ref` remains descriptive, never proof of identity. The database rejects role/source/authority combinations that violate this policy.

Only human credentials can change claim status, create reviewed claim relationships, or resolve possible conflicts. A reason and credential ID are recorded with each review action. An MCP adapter uses an agent credential and exposes no activation tool. Memory authority remains independent of action permission.

ADR 0012 permits candidate claims to be retrieved as explicitly provisional context before review. This does not promote them or raise their authority. Human credentials remain the only actors that can accept, verify, quarantine, or reject them through status changes. Rejection marks state while preserving the historical claim and evidence.

This role model is intentionally narrow. Production identity federation, credential storage, delegated organization administration, and action authorization require separate designs before shared deployment.
