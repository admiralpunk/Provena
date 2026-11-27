# ADR 0025: Optional local models and native Ollama

- Status: Accepted
- Date: 2026-11-27
- Amends: ADR 0012 and ADR 0013 (defaults only; trust rules unchanged)

## Context

Local quickstart downloads about 1.26 GB of Ollama models before the first memory can be extracted. It runs a CPU-only Ollama container (ADR 0022). On macOS, Ollama inside Docker cannot use the GPU, so extraction is slow even on machines where native Ollama would be fast. The download and the wait are the largest delays before a new user sees Provena work.

Agents can already store explicit memories without a Provena-side model. `memory_remember` and `memory_propose_claim` create low-authority candidate claims with evidence, and only a human reviewer can promote them (ADR 0007, ADR 0011, ADR 0012).

## Decision (proposed)

1. **Reuse native Ollama.** When an Ollama server is already reachable on the host, quickstart offers to use it instead of the container, and pulls the configured models there. This is the recommended path on macOS.
2. **Allow a model-free start.** `provena quickstart HOST --no-local-models` starts without Ollama:
   - Capture hooks still record every turn as an immutable event.
   - Automatic extraction reports that intelligence is not configured, which the API already does. Events remain without claims. Catch-up covers turns whose extraction failed because models were not ready yet (background downloads); turns captured with no provider configured at all are not extracted later (see Implementation notes).
   - Text retrieval needs a new non-semantic fallback. Today `GET /claims` with `q` returns `503 semantic retrieval is not configured` when no model is set. That makes the context hook retrieve nothing, because it fails open. The proposed fallback is PostgreSQL full-text search over claim propositions within the same exact scope. It is recorded with its own retrieval `method` so audits show which path served the result. Its limits are documented.
   - Explicit `memory_remember` calls keep working, and their claims stay low-authority candidates.
3. **Download models in the background.** When local models are enabled, quickstart may finish once the service is ready and keep downloading models in the background. `provena status` reports progress. Turns captured before models are ready are extracted later.
4. No change to trust: extraction is still only a candidate-producing step, authority is still computed by the server, and no model output becomes high authority.

## Consequences

- A first-time user can see capture, explain, and review within minutes, without a large download.
- The full-text fallback is new retrieval code. It must keep exact-scope filtering, candidate status, authority, and retrieval audit identical to the semantic path, and it needs real-PostgreSQL tests.
- Retrieval quality is lower until embeddings exist. The README and status output must say so plainly.
- Deferred extraction needs an idempotent catch-up job over stored events. Extraction runs are already recorded and reused per event (`reused` in the extraction response), which supports this.
- Native Ollama is outside Provena's control. Model names and versions must be checked before use, and failures must fall back to the model-free behavior.

## Implementation notes

- Full-text recall ORs the stemmed terms of the query (English configuration), because a whole user prompt is the typical query and requiring every word would almost never match. Results are ranked with `ts_rank` and recorded with retrieval `method = 'fulltext'`; migration `b8c2e4f61a35` adds that value to the `retrieval_method` check. The fallback is also used when the embedding call fails, for example while models download.
- `POST /scopes/{scope_id}/catch-up` retries events whose extraction failed for the current models and embeds eligible claims without an embedding for the current embedding model, in batches. It never changes a claim's status or evidence. `provena catch-up` repeats batches until nothing is pending.
- Claims created by `memory_remember` or `memory_propose_claim` were never embedded before this change, so semantic search could not find them. Catch-up embeds them.
- Captured turns that were never sent to a model (no extraction run recorded, as when no provider is configured) are not extracted by catch-up. Extracting them would need a decision about which stored events count as conversation turns.
- Native Ollama reuse checks from inside the API container that the host server answers. If it does not (on Linux, Ollama listens on 127.0.0.1 by default), quickstart falls back to the Ollama container. Missing models are pulled in the background with the host's `ollama` CLI when it is installed.
- `GET /intelligence` is unauthenticated and reports only the provider, model names, and readiness.
