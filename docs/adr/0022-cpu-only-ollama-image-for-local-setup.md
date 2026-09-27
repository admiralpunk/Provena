# ADR 0022: CPU-only Ollama image for local setup

- Status: Accepted
- Date: 2026-09-28
- Extends: ADR 0013 and ADR 0020

## Context

The official `ollama/ollama:0.34.2` Linux/amd64 image downloads about 3.71 GB, including GPU backends that a CPU-only local setup does not use. Provena's default `qwen2.5:1.5b` and `nomic-embed-text` models require another 1.26 GB. A self-built image would add image maintenance and a new Provena publisher. An already installed Ollama service remains possible, but the one-command quickstart manages its own Compose deployment.

The public `alpine/ollama:0.34.2` image is published by a third party, not by Ollama. Its Dockerfile copies Ollama's binary and CPU libraries from the official image into a smaller Wolfi-based image. The Linux/amd64 image downloads about 32 MB. The published image has a multi-architecture index for Linux/amd64 and Linux/arm64.

## Decision

Use `alpine/ollama:0.34.2@sha256:d6043eedd113d69b6cb2361aa7411988a63c69c5fd1e922974528c3b63b3a338` for both the Ollama server and model-pull service in the development and release Compose files. Pin the multi-architecture index digest so the same version tag cannot silently change the deployment. Keep the existing model names, data volume, API configuration, and authority rules.

The image is the default for Provena's local CPU setup. GPU acceleration requires a different Ollama deployment choice. A published package continues to download deployment files from its matching release; this decision takes effect for installed quickstart users when a release includes the updated Compose file.

## Verification

On Linux/amd64, both images reported Ollama 0.34.2. The Ollama binary and all 39 root-level files under `/usr/lib/ollama` had matching SHA-256 checksums. With the same model files, both images returned the same results for four extraction cases, including the same false positive and parsing failures, and returned 768-dimensional embeddings with matching sampled values. The CPU image passed model listing, model pulls through the separate client container, and model persistence across a restart. Linux/arm64 was listed in the published manifest but was not run in this verification.

## Consequences

CPU users avoid downloading roughly 3.68 GB of unused GPU components. Model downloads, CPU inference time, and extraction quality remain materially the same. The third-party publisher and Wolfi base add a supply-chain dependency; the pinned digest limits deployment drift but requires an intentional update to receive new Ollama or base-image fixes. The image choice does not change memory provenance, tenant isolation, or the rule that extracted claims remain candidates.
