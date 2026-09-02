# ADR 0009: Local MCP adapter delegates to the REST API

Status: Accepted

The Phase 2 MCP server runs over local stdio and calls the existing REST API using an agent credential supplied through environment variables. It offers exact-scope semantic search, event recording, candidate claim proposal, and explain. Search includes candidate claims with their provisional status and source authority under ADR 0012. It does not expose credential issuance, claim activation, or conflict review. This keeps one policy enforcement path in the API and prevents an agent tool from self-promoting low-trust content.

MCP does not passively capture a host's conversation or tool outputs. A host must call the record tool with source material; without a trusted host integration, those calls remain agent-supplied and low authority. A deterministic MCP client example proves the protocol and memory flow without adding an LLM dependency.
