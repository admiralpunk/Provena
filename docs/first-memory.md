# Verify your first captured memory with Codex

This walkthrough starts after `provena quickstart codex` completes. It follows one harmless preference from a Codex turn to the candidate claim and its source evidence in the local console.

## Check the service and open the console

Run the health check:

```bash
provena status
```

The output includes the API URL and liveness and readiness results. Quickstart also prints a `console_url`; open that complete URL in your browser so the console uses the scope quickstart created. `provena status` checks the API and database, but does not print the console URL.

If quickstart has just finished, restart Codex so it loads the Provena capture hook. In a new conversation, send a simple statement such as:

> I prefer mushrooms on pizza.

Let Codex finish its response. The hook captures the turn, then Provena attempts to extract candidate claims from the event.

## Find the candidate and inspect its source

In the console, open **Review Inbox**. Candidate claims waiting for review appear there. Select **Explain Claim** on the preference to open its explanation. You can also open **Memories** and select a claim to see the same explanation.

On **Explain claim**, check the candidate status near the claim title. In **SECTION B: WHY PROVENA BELIEVES IT**, follow the recorded stages. In **SECTION C: ORIGINAL EVIDENCE & UNTRUSTED SOURCE EVENTS**, verify the source event ID, source text, actor reference, and recorded time. The claim is provisional until a human reviews it; it is not automatically an approved fact or permission for an agent to act.

## If no candidate appears

Capture and extraction are separate. A captured event can exist without a candidate claim when extraction finds no durable fact. The first local quickstart also downloads about 1.26 GB of models, and extraction can take several minutes while those models are being set up. The captured event remains even if extraction has not produced a claim yet. See the [quickstart setup notes](../README.md#get-started) and the [local model setup and logs](development.md#run-the-api-and-console) before treating an empty Review Inbox as a capture failure.

Not every sentence becomes a claim. Provena proposes only candidate facts that pass extraction; each stays linked to its source event and awaits review.
