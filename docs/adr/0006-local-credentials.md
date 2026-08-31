# ADR 0006: Local bootstrap and tenant API keys

Status: Accepted

Phase 1 uses a configured bootstrap token to create organizations and returns one randomly generated API key per organization. Only a SHA-256 digest is stored. Subsequent requests derive organization identity from the key rather than a client-supplied tenant ID. This is sufficient for local integration and tenant-isolation tests, but it is not a production identity system. Production deployment needs credential rotation, roles, rate limits, and a restricted organization-provisioning path. A tenant key cannot assert high-authority tool observations.
