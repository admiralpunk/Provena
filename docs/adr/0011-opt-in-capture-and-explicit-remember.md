# ADR 0011: Opt-in capture and atomic explicit remember

Status: Accepted

Conversation capture is an integration behavior, not an MCP server capability. A host must opt in and send each turn it wants preserved. The API provides one atomic write that saves a source event and, when the caller supplies a structured proposition, a candidate claim with evidence to that event. A successful response confirms both IDs, scope, status, and authority. A failed claim creation rolls back the event too. The API does not infer claims from arbitrary text.

The MCP adapter exposes a convenience `memory_remember` tool for an agent's own inference. It cannot assert that it directly authenticated a user. A host capture helper may submit user turns as `user_statement`, but with an agent credential those events remain low authority and are visibly attributable to that agent credential. A future trusted host identity design is required before host-attested user statements can receive medium authority without holding a human review credential.

All new claims remain candidates. Conversation capture never activates them; only a human credential can review status. Under ADR 0012, exact-scope search can return candidates as visibly provisional context. The raw event is preserved even when no proposition is supplied. Hosts choose whether to capture turns. Configured extraction may propose claims automatically, but it never changes their status.

Codex integration uses its `UserPromptSubmit` command hook. The hook records the exact submitted prompt as an event, attributes it to the Codex session and turn, emits no model context, and does not create a claim. It fails open so memory availability cannot reject or alter a user's prompt. Hook environment variables are inherited from the Codex process and are configured separately from MCP subprocess environment settings.
