# ADR 0014: Model-agnostic agent integration

- Status: Accepted
- Date: 2026-09-20

## Context

Provena's storage and inference pipeline is independent of the conversational model, but the first automatic lifecycle adapter was named for Codex. Claude Code, Gemini CLI, Codex, and custom hosts expose different hook event names while all can use MCP. Memories must remain shared across host sessions without confusing a host session with a memory visibility scope.

## Decision

MCP and REST are the portable product boundaries. The MCP server exposes `memory_context` for per-request retrieval and `memory_capture_turn` for hosts without lifecycle hooks. Server instructions ask MCP clients to retrieve context at the start of a request. Explicit remember, search, and explain tools remain available.

A single fail-open command adapter normalizes Codex and Claude Code `UserPromptSubmit`/`Stop` events and Gemini CLI `BeforeAgent`/`AfterAgent` events. Context retrieval always uses the configured Provena scope. Capture records both sides as immutable events and requests local extraction.

Each external conversation is represented by a Provena session with an idempotent identity of `host:external-session-id`. Sessions provide provenance only. They do not restrict retrieval visibility. Claims are shared between Claude, Gemini, Codex, and later clients when those clients authenticate to the same organization and use the same scope.

Host and model names never change source authority. Agent-mediated user text and assistant output remain low authority, extracted claims remain candidates, and retrieved content remains untrusted context rather than permission to act.

## Consequences

Clients with supported hooks receive automatic context and capture. Other MCP clients can call the portable tools explicitly. A host that neither runs hooks nor follows MCP server instructions cannot be forced by Provena to capture or retrieve turns. Session identity is durable and attributable without creating separate claim stores per model.

ADR 0020 adds a packaged Codex installer and local quickstart while retaining these model-agnostic MCP, REST, and lifecycle boundaries.
