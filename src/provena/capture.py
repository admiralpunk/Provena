"""Opt-in host hook for preserving conversation turns through the REST API."""

from typing import Any, Literal, TypedDict
from uuid import UUID

import httpx


class Proposition(TypedDict):
    subject: str
    predicate: str
    value: dict[str, Any]


class ConversationCapture:
    def __init__(self, base_url: str, api_key: str, scope_id: str, *, enabled: bool = False, session_id: str | None = None, session_external_ref: str | None = None, http: httpx.Client | None = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.scope_id = str(UUID(scope_id))
        self.session_id = str(UUID(session_id)) if session_id else None
        self.session_external_ref = session_external_ref
        if self.session_id and self.session_external_ref:
            raise ValueError("use session_id or session_external_ref, not both")
        self.enabled = enabled
        self.http = http or httpx.Client(timeout=10)

    def record_turn(self, role: Literal["user", "assistant"], text: str, proposition: Proposition | None = None, *, actor_ref: str | None = None, extract: bool = False) -> dict[str, Any] | None:
        """The host calls this for turns it elects to capture; proposals remain candidates."""
        if not self.enabled:
            return None
        if role not in ("user", "assistant"):
            raise ValueError("role must be user or assistant")
        if not text.strip():
            raise ValueError("turn text is required")
        body: dict[str, Any] = {
            "scope_id": self.scope_id,
            "source_kind": "user_statement" if role == "user" else "assistant_inference",
            "text": text,
        }
        if self.session_id:
            body["session_id"] = self.session_id
        if self.session_external_ref:
            body["session_external_ref"] = self.session_external_ref
        if actor_ref:
            body["actor_ref"] = actor_ref
        if proposition is not None:
            body["proposition"] = proposition
        response = self.http.post(f"{self.base_url}/memories", headers={"X-API-Key": self.api_key}, json=body)
        if response.is_error:
            raise ValueError(f"Provena API returned {response.status_code}: {response.json().get('detail', 'request failed')}")
        result = response.json()
        if extract:
            extraction = self.http.post(f"{self.base_url}/events/{result['event']['id']}/extract", headers={"X-API-Key": self.api_key})
            if extraction.is_error:
                raise ValueError(f"Provena extraction returned {extraction.status_code}: {extraction.json().get('detail', 'request failed')}")
            result["extraction"] = extraction.json()
        return result
