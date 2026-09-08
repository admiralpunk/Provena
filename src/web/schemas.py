from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ..core.domain import ClaimStatus, ConflictDecision, CredentialRole, RelationshipKind, ScopeKind, SourceKind


class OrganizationIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class CredentialIn(BaseModel):
    role: CredentialRole
    label: str = Field(min_length=1, max_length=200)


class ReviewIn(BaseModel):
    decision: ConflictDecision
    reason: str = Field(min_length=1, max_length=2000)
    superseding_claim_id: UUID | None = None

    @model_validator(mode="after")
    def check_direction(self):
        if (self.decision == ConflictDecision.TEMPORAL_CHANGE) != (self.superseding_claim_id is not None):
            raise ValueError("temporal_change requires superseding_claim_id; other decisions must omit it")
        return self


class NameIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class ScopeIn(BaseModel):
    kind: ScopeKind
    project_id: UUID
    parent_id: UUID
    key: str = Field(min_length=1, max_length=200)


class SessionIn(BaseModel):
    scope_id: UUID
    agent_id: UUID | None = None
    external_ref: str | None = Field(default=None, max_length=200)


class EventIn(BaseModel):
    scope_id: UUID
    session_id: UUID | None = None
    source_kind: SourceKind
    actor_ref: str | None = Field(default=None, max_length=200)
    payload: dict[str, Any]


class ClaimIn(BaseModel):
    scope_id: UUID
    subject: str = Field(min_length=1, max_length=300)
    predicate: str = Field(min_length=1, max_length=200)
    value: dict[str, Any]
    evidence_event_ids: list[UUID] = Field(min_length=1)
    valid_from: datetime | None = None
    valid_to: datetime | None = None

    @model_validator(mode="after")
    def check_times(self):
        for value in (self.valid_from, self.valid_to):
            if value is not None and value.tzinfo is None:
                raise ValueError("validity timestamps require an offset")
        if self.valid_from and self.valid_to and self.valid_from >= self.valid_to:
            raise ValueError("valid_from must precede valid_to")
        if len(set(self.evidence_event_ids)) != len(self.evidence_event_ids):
            raise ValueError("duplicate evidence event")
        return self


class PropositionIn(BaseModel):
    subject: str = Field(min_length=1, max_length=300)
    predicate: str = Field(min_length=1, max_length=200)
    value: dict[str, Any]
    valid_from: datetime | None = None
    valid_to: datetime | None = None

    @model_validator(mode="after")
    def check_times(self):
        for value in (self.valid_from, self.valid_to):
            if value is not None and value.tzinfo is None:
                raise ValueError("validity timestamps require an offset")
        if self.valid_from and self.valid_to and self.valid_from >= self.valid_to:
            raise ValueError("valid_from must precede valid_to")
        return self


class MemoryIn(BaseModel):
    scope_id: UUID
    session_id: UUID | None = None
    session_external_ref: str | None = Field(default=None, min_length=1, max_length=200)
    source_kind: SourceKind
    actor_ref: str | None = Field(default=None, max_length=200)
    text: str = Field(min_length=1)
    proposition: PropositionIn | None = None

    @model_validator(mode="after")
    def check_text(self):
        if not self.text.strip():
            raise ValueError("memory text is required")
        if self.session_id is not None and self.session_external_ref is not None:
            raise ValueError("use session_id or session_external_ref, not both")
        return self


class StatusIn(BaseModel):
    status: ClaimStatus
    reason: str = Field(min_length=1, max_length=2000)


class RelationshipIn(BaseModel):
    from_claim_id: UUID
    to_claim_id: UUID
    kind: RelationshipKind
    reason: str = Field(min_length=1, max_length=2000)
