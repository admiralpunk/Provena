"""Opt-in host hook for preserving conversation turns through the REST API."""

from typing import Any, Literal, TypedDict
from uuid import UUID

import httpx


class Proposition(TypedDict):
    subject: str
    predicate: str
    value: dict[str, Any]


class ConversationCapture:
    def __init__(self, base_url: str, api_key: str, scope_id: str, *, enabled: bool = False, session_id: str | None = None, http: httpx.Client | None = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.scope_id = str(UUID(scope_id))
        self.session_id = str(UUID(session_id)) if session_id else None
        self.enabled = enabled
        self.http = http or httpx.Client(timeout=10)

    def record_turn(self, role: Literal["user", "assistant"], text: str, proposition: Proposition | None = None) -> dict[str, Any] | None:
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
        if proposition is not None:
            body["proposition"] = proposition
        response = self.http.post(f"{self.base_url}/memories", headers={"X-API-Key": self.api_key}, json=body)
        if response.is_error:
            raise ValueError(f"Provena API returned {response.status_code}: {response.json().get('detail', 'request failed')}")
        return response.json()
