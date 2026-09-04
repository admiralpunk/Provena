# ADR 0012: Candidate claims are retrievable as provisional context

Status: Accepted

Candidate claims may participate in retrieval before human review. Every retrieval result must expose claim status and evidence authority, and integrations must describe candidates as provisional. Candidate memory remains context only and never grants permission to act. Active, verified, and conflicted claims remain retrievable; quarantined, expired, superseded, and deleted claims are excluded. A rejected candidate transitions through the audited status workflow to `deleted` or `quarantined`; its claim, evidence, extraction run, and actions remain preserved.

Automatic extraction operates on immutable user and assistant events. The configured extraction model returns zero or more structured candidate claims. Each claim links to its source event, receives an append-only extraction action containing the model and confidence, and has a model-derived embedding stored separately from the immutable proposition. Extraction runs record event, extraction model, embedding model, result, and failure. Repeating the same model pair for an event reuses the recorded run.

Semantic retrieval uses `text-embedding-3-small` vectors in PostgreSQL with pgvector and exact tenant and scope filters. The query text and retrieval method are audited. Embeddings are derived indexes and never evidence. The initial extraction provider is OpenAI Responses structured output, configured with a separate API key. Deterministic tests inject a fake provider and never depend on an LLM or network. Failed extraction attempts remain immutable and do not prevent retry. Extraction locks the source event during an attempt and reuses only a completed run for the same model pair, preventing concurrent duplicate claims.

Codex `UserPromptSubmit` and `Stop` hooks capture both sides as immutable events and request extraction in background hooks. A separate synchronous prompt hook retrieves up to five relevant claims and supplies them as explicitly untrusted, attributed context. Capture or retrieval failure does not block the Codex turn.

This changes ADR 0007's prior rule that only reviewed states are usable for retrieval. Human review still controls state promotion, verification, quarantine, and deletion. The UI must prioritize candidate review and show the original evidence before accepting or rejecting a claim.
