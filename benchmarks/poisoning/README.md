# Memory-poisoning benchmark

Agent memory is an attack surface. A web page, README, or tool result can plant a "fact" that the agent repeats, a memory system stores, and a later session acts on. Research in 2026 measured this directly: systems that write and recall memory aggressively are easier to exploit, and prompt-injection defenses only partly cover memory.

This benchmark checks what Provena does when someone tries to poison its memory. It records observed behavior against specific trust properties, including what Provena does **not** do.

**Latest result:** 127 of 127 checks passed across 23 cases. See [RESULTS.md](RESULTS.md) for the table and [results.json](results.json) for every observation.

## What Provena does and does not do

Provena does **not** block a planted fact. If the assistant repeats something it read, Provena stores it and later sessions receive it. What Provena adds is the receipt:

- It is labeled as an unreviewed **candidate**, from **assistant_inference**, with **low** authority.
- It traces back to the exact words that produced it.
- Every delivery to an agent is audited.
- The agent cannot promote it. Only a human reviewer can, and quarantining it stops delivery while keeping the evidence.
- It cannot leak into another project or organization.
- If it contradicts something the user said, the conflict is recorded and both versions are delivered with their sources.

Whether the agent then trusts a low-authority candidate is up to the agent and its instructions. Provena gives it the information to decide; it does not decide for it.

## Cases

| Category | Cases | What is attempted |
|---|---|---|
| Indirect injection through assistant output | 8 | The assistant repeats a rule from external content (auto-merge PRs, commit `.env` files, skip tests, untrusted package registry, and others). |
| Instructions smuggled into memory values | 5 | A memory's value contains an instruction ("ignore all previous instructions", fake system messages, exfiltration requests, tag-escape attempts). |
| Scope and tenant isolation | 5 | The same poison is planted in a neighboring project and in another organization. |
| Contradicting a fact the user stated | 5 | A planted claim contradicts something the user said earlier. |

Each case runs several checks. The categories follow the write channels and attack types described in the research below. The cases are written for this benchmark and are not taken from those datasets.

## Method

- **Real PostgreSQL**, migrated with Alembic, through Provena's REST API and the actual context hook that Claude Code, Codex, and Gemini CLI run.
- **Deterministic.** Memories are written explicitly instead of by a model, and recall uses the full-text path (`MEMORY_PROVIDER=none`). The same database state always gives the same result.
- **Mutation-tested.** The checks were confirmed to fail when a protection is removed:

  | Protection removed | Checks that failed |
  |---|---|
  | Conflict detection | 10 (both conflict checks in every contradiction case) |
  | The context hook's untrusted-memory notice and JSON framing | 20 (every smuggled-instruction check) |
  | The API's human-reviewer check | 0, because a database trigger independently refuses status changes from non-human credentials |

## Limits

- **Semantic retrieval is not exercised.** Results for embedding-based recall may differ in what is delivered, not in how it is labeled.
- **No model extraction.** A real extractor might rephrase or drop a planted fact; this benchmark tests the store and its labels, not the model.
- **Provena only.** No other memory system has been run through it, so there are no comparison numbers. The harness is built so others can be added (below).
- **Agent behavior is out of scope.** The benchmark checks what the agent is given, not what the agent does with it.

## Run it

Use a disposable database: the run creates its own organizations and projects, and Provena never deletes evidence.

```bash
DATABASE_URL=postgresql+psycopg://... .venv/bin/alembic upgrade head
.venv/bin/python benchmarks/poisoning/run.py --database-url postgresql+psycopg://... \
  --json benchmarks/poisoning/results.json --markdown benchmarks/poisoning/RESULTS.md
```

No Docker? Let Provena start a private PostgreSQL from your system packages, as described in "Tests and release checks" in [docs/development.md](../../docs/development.md). The test suite also runs this benchmark whenever `TEST_DATABASE_URL` is set, so CI fails if any of these properties regress.

## Add another memory system

`ProvenaAdapter` in [harness.py](harness.py) has a small surface: create a tenant and a scope, remember a fact with its source text, recall, explain, change a status, and fetch the agent's injected context. An adapter for another system implements the same methods. Where a system has no equivalent (for example, no source labels or no review step), record that as an observed result rather than skipping the check. Contributions are welcome; please open an issue first.

## Related research

- *From Untrusted Input to Trusted Memory: A Systematic Study of Memory Poisoning Attacks in LLM Agents* (arXiv [2606.04329](https://arxiv.org/abs/2606.04329)). Introduces MPBench: four write channels, nine structural vulnerabilities, about 50% average attack success, and incomplete coverage by prompt-injection defenses.
- *MemPoison* (arXiv [2607.14651](https://arxiv.org/abs/2607.14651), NeurIPS 2026). 1,227 validated cases across attack types, injection channels, and memory substrates.
- Sleeper memory poisoning (arXiv [2605.15338](https://arxiv.org/abs/2605.15338)). A web page plants a fabricated memory that stays dormant until it shapes a later conversation.
