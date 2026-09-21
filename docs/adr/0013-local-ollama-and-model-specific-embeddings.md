# ADR 0013: Local Ollama and model-specific embeddings

- Status: Accepted
- Date: 2026-09-20
- Supersedes: the OpenAI default in ADR 0012

## Context

Automatic extraction and semantic retrieval initially called OpenAI. This made a local Provena deployment depend on a second paid API and fixed the database vector type to one provider's 1,536 dimensions. Extraction and embeddings are derived indexes; immutable events and their evidence remain the authority.

## Decision

Ollama is the default memory intelligence provider. Local development runs Ollama as one Docker Compose service, uses `qwen2.5:1.5b` for structured fact extraction, and uses `nomic-embed-text` for embeddings. OpenAI remains an explicit optional provider.

Provider model identifiers stored in extraction and embedding records are namespaced, such as `ollama:qwen2.5:1.5b`. Embedding rows store a generated dimension derived from the vector. Semantic retrieval compares only embeddings from the configured model with the query's dimension.

The initial HNSW index is removed. PostgreSQL performs exact cosine ordering after tenant, scope, model, and dimension filtering. At measured scale, a model-specific expression or partial index may be added in a later migration.

Ollama output creates candidate claims only. It cannot increase source authority, activate a claim, grant action permission, alter an event, or remove evidence. Failed attempts remain append-only extraction runs and can be retried.

## Consequences

Local extraction and retrieval need no OpenAI account or API credits. The Ollama server and model weights consume local disk, memory, and CPU or GPU resources. Small local models can extract facts incorrectly, so attribution, candidate status, human review, and explain remain required. Exact vector scans favor correctness and provider flexibility over large-scale retrieval speed.
