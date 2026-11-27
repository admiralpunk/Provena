"""Render a claim's explain trail as a terminal receipt (`provena why`, `provena demo`)."""

from __future__ import annotations

import json
import textwrap
from typing import Any, Mapping, Sequence

WIDTH = 78
LABEL = 11


def _when(value: Any) -> str:
    """Format an API timestamp in UTC, whatever offset the server used."""
    from datetime import datetime, timezone

    text = str(value or "")
    if not text:
        return "unknown time"
    try:
        moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return text
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _value(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _row(label: str, text: str) -> list[str]:
    lines = textwrap.wrap(text, WIDTH - LABEL) or [""]
    return [f"{label:<{LABEL}}{lines[0]}", *(" " * LABEL + line for line in lines[1:])]


def _quote(text: str) -> list[str]:
    body = text.strip().replace("\n", " ")
    if len(body) > 400:
        body = body[:397] + "..."
    return [" " * LABEL + line for line in textwrap.wrap(f"“{body}”", WIDTH - LABEL)]


def trust_notes(explanation: Mapping[str, Any]) -> list[str]:
    """Plain-language reasons to treat a memory with care. Facts only, from the explain trail."""

    claim = explanation["claim"]
    events = [item["event"] for item in explanation.get("evidence", [])]
    notes: list[str] = []
    if claim["status"] == "candidate":
        notes.append("candidate: no human has reviewed this memory")
    if claim["status"] in ("conflicted", "superseded", "quarantined", "expired"):
        notes.append(f"status is {claim['status']}: do not rely on it as current")
    if events and all(event.get("authority") == "low" for event in events):
        notes.append("low authority: reported through an agent credential, not by an authenticated person")
    if events and all(event.get("source_kind") == "assistant_inference" for event in events):
        notes.append("came from the assistant's own words, not from the user")
    if any(rel.get("kind") in ("contradicts", "related_to") for rel in explanation.get("relationships", [])):
        notes.append("has a conflict or possible conflict with another memory")
    return notes


def render_receipt(explanation: Mapping[str, Any], deliveries: Sequence[Mapping[str, Any]] = ()) -> str:
    claim = explanation["claim"]
    lines = ["PROVENA RECEIPT " + "-" * (WIDTH - 16)]
    lines += _row("claim", f"{claim['subject']}.{claim['predicate']} = {_value(claim['value'])}")
    validity = "open-ended"
    if claim.get("valid_from") or claim.get("valid_to"):
        validity = f"{_when(claim.get('valid_from')) if claim.get('valid_from') else '...'} to {_when(claim.get('valid_to')) if claim.get('valid_to') else '...'}"
    lines += _row("status", f"{claim['status']} (version {claim.get('status_version', 0)}), valid {validity}")
    lines += _row("id", str(claim["id"]))

    for index, item in enumerate(explanation.get("evidence", [])):
        event = item["event"]
        credential = event.get("credential") or {}
        who = f"{credential.get('role', 'unknown')} credential “{credential.get('label', '?')}”" if credential else "unknown credential"
        lines += _row("source" if index == 0 else "", f"{event['source_kind']}, authority {event['authority']}, recorded {_when(event.get('recorded_at'))}")
        payload = event.get("payload") or {}
        text = payload.get("text") if isinstance(payload, dict) else None
        lines += _quote(text if isinstance(text, str) else _value(payload))
        lines += _row("", f"via {who}" + (f", {event['actor_ref']}" if event.get("actor_ref") else ""))

    extractions = [run for run in explanation.get("extractions", []) if run.get("status") == "completed"]
    if extractions:
        run = extractions[-1]
        lines += _row("extracted", f"by {run['extractor_model']} on {_when(run.get('created_at'))}")
    else:
        lines += _row("extracted", "not by a model: stated explicitly through memory_remember or the API")

    reviews = [action for action in explanation.get("actions", []) if action.get("action") == "status_changed"]
    if reviews:
        for index, action in enumerate(reviews):
            lines += _row("review" if index == 0 else "", f"{action.get('old_status')} -> {action.get('new_status')} by {action.get('actor_ref')}: {action.get('reason') or 'no reason given'}")
    else:
        lines += _row("review", "none yet")

    relationships = explanation.get("relationships", [])
    if relationships:
        for index, relation in enumerate(relationships):
            lines += _row("conflicts" if index == 0 else "", f"{relation['kind']} {relation['to_claim_id'] if str(relation['from_claim_id']) == str(claim['id']) else relation['from_claim_id']}: {relation.get('reason') or ''}".rstrip(": "))
    else:
        lines += _row("conflicts", "none recorded")

    total = len(explanation.get("retrievals", []))
    if total == 0:
        lines += _row("delivered", "never delivered to an agent")
    else:
        lines += _row("delivered", f"{total} time{'s' if total != 1 else ''} to an agent")
        for detail in deliveries:
            retrieval = detail.get("retrieval", detail)
            query = retrieval.get("query_text") or (f"predicate {retrieval.get('predicate')}" if retrieval.get("predicate") else "exact-scope listing")
            lines += _row("", f"{_when(retrieval.get('created_at'))} for “{query}” ({retrieval.get('method', '?')})")

    notes = trust_notes(explanation)
    for index, note in enumerate(notes):
        lines += _row("trust" if index == 0 else "", f"! {note}")
    lines.append("-" * WIDTH)
    return "\n".join(lines)
