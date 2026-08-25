from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, Computed, ForeignKeyConstraint, Index, PrimaryKeyConstraint, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import DateTime, Integer, String, Text
from pgvector.sqlalchemy import Vector

from .domain import ClaimStatus


class Base(DeclarativeBase):
    pass


def uid():
    return mapped_column(PGUUID(as_uuid=True), default=uuid4)


def org_id():
    return mapped_column(PGUUID(as_uuid=True), nullable=False)


def created():
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Organization(Base):
    __tablename__ = "organization"
    id: Mapped[UUID] = uid()
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = created()
    __table_args__ = (PrimaryKeyConstraint("id"),)


class Credential(Base):
    __tablename__ = "credential"
    id: Mapped[UUID] = uid()
    organization_id: Mapped[UUID] = org_id()
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = created()
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (PrimaryKeyConstraint("id"), UniqueConstraint("organization_id", "id"), ForeignKeyConstraint(["organization_id"], ["organization.id"]), CheckConstraint("role IN ('agent','human','tool')", name="credential_role"),)


class Project(Base):
    __tablename__ = "project"
    id: Mapped[UUID] = uid()
    organization_id: Mapped[UUID] = org_id()
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = created()
    __table_args__ = (PrimaryKeyConstraint("id"), UniqueConstraint("organization_id", "id"), UniqueConstraint("organization_id", "name"), ForeignKeyConstraint(["organization_id"], ["organization.id"]),)


class Agent(Base):
    __tablename__ = "agent"
    id: Mapped[UUID] = uid()
    organization_id: Mapped[UUID] = org_id()
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = created()
    __table_args__ = (PrimaryKeyConstraint("id"), UniqueConstraint("organization_id", "id"), ForeignKeyConstraint(["organization_id"], ["organization.id"]),)


class Scope(Base):
    __tablename__ = "scope"
    id: Mapped[UUID] = uid()
    organization_id: Mapped[UUID] = org_id()
    project_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    parent_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    key: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = created()
    __table_args__ = (
        PrimaryKeyConstraint("id"), UniqueConstraint("organization_id", "id"),
        UniqueConstraint("organization_id", "parent_id", "kind", "key"),
        ForeignKeyConstraint(["organization_id"], ["organization.id"]),
        ForeignKeyConstraint(["organization_id", "project_id"], ["project.organization_id", "project.id"]),
        ForeignKeyConstraint(["organization_id", "parent_id"], ["scope.organization_id", "scope.id"]),
        CheckConstraint("kind IN ('organization','project','branch')", name="scope_kind"),
        CheckConstraint("(kind = 'organization' AND parent_id IS NULL AND project_id IS NULL) OR (kind <> 'organization' AND parent_id IS NOT NULL AND project_id IS NOT NULL)", name="scope_shape"),
        Index("uq_org_root_scope", "organization_id", unique=True, postgresql_where=text("kind = 'organization'")),
        Index("uq_project_scope", "organization_id", "project_id", unique=True, postgresql_where=text("kind = 'project'")),
    )


class Session(Base):
    __tablename__ = "session"
    id: Mapped[UUID] = uid()
    organization_id: Mapped[UUID] = org_id()
    agent_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    scope_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    external_ref: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = created()
    __table_args__ = (PrimaryKeyConstraint("id"), UniqueConstraint("organization_id", "id"), UniqueConstraint("organization_id", "scope_id", "external_ref", name="uq_session_external_ref"), ForeignKeyConstraint(["organization_id", "scope_id"], ["scope.organization_id", "scope.id"]), ForeignKeyConstraint(["organization_id", "agent_id"], ["agent.organization_id", "agent.id"]),)


class Event(Base):
    __tablename__ = "event"
    id: Mapped[UUID] = uid()
    organization_id: Mapped[UUID] = org_id()
    scope_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    session_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    credential_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    source_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    authority: Mapped[str] = mapped_column(String(16), nullable=False)
    actor_ref: Mapped[str | None] = mapped_column(String(200))
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    recorded_at: Mapped[datetime] = created()
    __table_args__ = (PrimaryKeyConstraint("id"), UniqueConstraint("organization_id", "id"), ForeignKeyConstraint(["organization_id", "scope_id"], ["scope.organization_id", "scope.id"]), ForeignKeyConstraint(["organization_id", "session_id"], ["session.organization_id", "session.id"]), ForeignKeyConstraint(["organization_id", "credential_id"], ["credential.organization_id", "credential.id"]), CheckConstraint("source_kind IN ('user_statement','user_correction','tool_observation','test_output','assistant_inference','hypothesis')", name="event_source_kind"), CheckConstraint("authority IN ('high','medium','low','ephemeral')", name="event_authority_value"),)


class Claim(Base):
    __tablename__ = "claim"
    id: Mapped[UUID] = uid()
    organization_id: Mapped[UUID] = org_id()
    scope_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    subject: Mapped[str] = mapped_column(String(300), nullable=False)
    predicate: Mapped[str] = mapped_column(String(200), nullable=False)
    value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=ClaimStatus.CANDIDATE.value)
    status_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    recorded_at: Mapped[datetime] = created()
    __table_args__ = (PrimaryKeyConstraint("id"), UniqueConstraint("organization_id", "id"), ForeignKeyConstraint(["organization_id", "scope_id"], ["scope.organization_id", "scope.id"]), CheckConstraint("status IN ('candidate','active','verified','conflicted','superseded','quarantined','expired','ephemeral','deleted')", name="claim_status"), CheckConstraint("status_version >= 0", name="claim_status_version"), CheckConstraint("valid_from IS NULL OR valid_to IS NULL OR valid_from < valid_to", name="claim_valid_interval"), Index("ix_claim_lookup", "organization_id", "scope_id", "subject", "predicate"),)


class Evidence(Base):
    __tablename__ = "evidence"
    id: Mapped[UUID] = uid()
    organization_id: Mapped[UUID] = org_id()
    claim_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    event_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = created()
    __table_args__ = (PrimaryKeyConstraint("id"), UniqueConstraint("organization_id", "claim_id", "event_id"), ForeignKeyConstraint(["organization_id", "claim_id"], ["claim.organization_id", "claim.id"]), ForeignKeyConstraint(["organization_id", "event_id"], ["event.organization_id", "event.id"]),)


class ExtractionRun(Base):
    __tablename__ = "extraction_run"
    id: Mapped[UUID] = uid()
    organization_id: Mapped[UUID] = org_id()
    event_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    extractor_model: Mapped[str] = mapped_column(String(100), nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    facts: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created()
    __table_args__ = (
        PrimaryKeyConstraint("id"),
        UniqueConstraint("organization_id", "id"),
        ForeignKeyConstraint(["organization_id", "event_id"], ["event.organization_id", "event.id"]),
        CheckConstraint("status IN ('completed','failed')", name="extraction_status"),
        Index("ix_extraction_event_models", "organization_id", "event_id", "extractor_model", "embedding_model"),
    )


class ClaimEmbedding(Base):
    __tablename__ = "claim_embedding"
    id: Mapped[UUID] = uid()
    organization_id: Mapped[UUID] = org_id()
    claim_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    dimensions: Mapped[int] = mapped_column(Integer, Computed("vector_dims(embedding)", persisted=True), nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(), nullable=False)
    created_at: Mapped[datetime] = created()
    __table_args__ = (
        PrimaryKeyConstraint("id"),
        UniqueConstraint("organization_id", "id"),
        UniqueConstraint("organization_id", "claim_id", "model"),
        ForeignKeyConstraint(["organization_id", "claim_id"], ["claim.organization_id", "claim.id"]),
        CheckConstraint("dimensions > 0", name="embedding_dimensions"),
    )


class ClaimRelationship(Base):
    __tablename__ = "claim_relationship"
    id: Mapped[UUID] = uid()
    organization_id: Mapped[UUID] = org_id()
    from_claim_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    to_claim_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = created()
    __table_args__ = (PrimaryKeyConstraint("id"), UniqueConstraint("organization_id", "id"), UniqueConstraint("organization_id", "from_claim_id", "to_claim_id", "kind"), ForeignKeyConstraint(["organization_id", "from_claim_id"], ["claim.organization_id", "claim.id"]), ForeignKeyConstraint(["organization_id", "to_claim_id"], ["claim.organization_id", "claim.id"]), CheckConstraint("from_claim_id <> to_claim_id", name="relationship_distinct"), CheckConstraint("kind IN ('supports','contradicts','supersedes','derived_from','related_to')", name="relationship_kind"),)


class ConflictReview(Base):
    __tablename__ = "conflict_review"
    id: Mapped[UUID] = uid()
    organization_id: Mapped[UUID] = org_id()
    case_relationship_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    reviewer_credential_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    decision: Mapped[str] = mapped_column(String(32), nullable=False)
    superseding_claim_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = created()
    __table_args__ = (PrimaryKeyConstraint("id"), UniqueConstraint("organization_id", "case_relationship_id"), ForeignKeyConstraint(["organization_id", "case_relationship_id"], ["claim_relationship.organization_id", "claim_relationship.id"]), ForeignKeyConstraint(["organization_id", "reviewer_credential_id"], ["credential.organization_id", "credential.id"]), ForeignKeyConstraint(["organization_id", "superseding_claim_id"], ["claim.organization_id", "claim.id"]), CheckConstraint("decision IN ('contradiction','temporal_change','dismissed')", name="conflict_decision"),)


class MemoryAction(Base):
    __tablename__ = "memory_action"
    id: Mapped[UUID] = uid()
    organization_id: Mapped[UUID] = org_id()
    claim_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    version: Mapped[int | None] = mapped_column(Integer)
    old_status: Mapped[str | None] = mapped_column(String(32))
    new_status: Mapped[str | None] = mapped_column(String(32))
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    actor_ref: Mapped[str] = mapped_column(String(200), nullable=False)
    credential_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    created_at: Mapped[datetime] = created()
    __table_args__ = (PrimaryKeyConstraint("id"), UniqueConstraint("organization_id", "claim_id", "version"), ForeignKeyConstraint(["organization_id", "claim_id"], ["claim.organization_id", "claim.id"]), ForeignKeyConstraint(["organization_id", "credential_id"], ["credential.organization_id", "credential.id"]),)


class RetrievalEvent(Base):
    __tablename__ = "retrieval_event"
    id: Mapped[UUID] = uid()
    organization_id: Mapped[UUID] = org_id()
    scope_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    predicate: Mapped[str | None] = mapped_column(String(200))
    query_text: Mapped[str | None] = mapped_column(Text)
    method: Mapped[str] = mapped_column(String(32), nullable=False, default="exact")
    actor_ref: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = created()
    __table_args__ = (PrimaryKeyConstraint("id"), UniqueConstraint("organization_id", "id"), ForeignKeyConstraint(["organization_id", "scope_id"], ["scope.organization_id", "scope.id"]),)


class RetrievalItem(Base):
    __tablename__ = "retrieval_item"
    organization_id: Mapped[UUID] = org_id()
    retrieval_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    claim_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    __table_args__ = (PrimaryKeyConstraint("retrieval_id", "claim_id"), ForeignKeyConstraint(["organization_id", "retrieval_id"], ["retrieval_event.organization_id", "retrieval_event.id"]), ForeignKeyConstraint(["organization_id", "claim_id"], ["claim.organization_id", "claim.id"]),)
