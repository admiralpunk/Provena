# ADR 0001: One service and PostgreSQL as system of record

Status: Accepted

Phase 1 uses one FastAPI service and PostgreSQL for events, claims, evidence, audit, and raw JSON payloads. This permits atomic claim/evidence creation and status/action updates. Object storage, pgvector indexes, and additional services wait for a concrete requirement and consistency design.

