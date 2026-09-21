# ADR 0010: Commit before responding; enforce human status actions in PostgreSQL

Status: Accepted

The API commits each request's transaction before sending its HTTP response. A live MCP smoke test exposed that committing after the response allowed a following request to miss a newly created scope. FastAPI's function-scoped yield dependency provides the earlier transaction exit. Deferred database constraints also fail before the client sees success.

The database requires every status transition to match a new, versioned `MemoryAction`. A further insert guard requires an active human credential on status-change actions. This preserves the review boundary even when an application code path writes actions directly. Legacy actions created before credential migration remain historical records; they cannot justify a future transition because versions cannot be reused.
