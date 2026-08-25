from enum import StrEnum


class ScopeKind(StrEnum):
    ORGANIZATION = "organization"
    PROJECT = "project"
    BRANCH = "branch"


class SourceKind(StrEnum):
    USER_STATEMENT = "user_statement"
    USER_CORRECTION = "user_correction"
    TOOL_OBSERVATION = "tool_observation"
    TEST_OUTPUT = "test_output"
    ASSISTANT_INFERENCE = "assistant_inference"
    HYPOTHESIS = "hypothesis"


class Authority(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    EPHEMERAL = "ephemeral"


class CredentialRole(StrEnum):
    AGENT = "agent"
    HUMAN = "human"
    TOOL = "tool"


SOURCE_AUTHORITY = {
    CredentialRole.AGENT: {
        SourceKind.USER_STATEMENT: Authority.LOW,
        SourceKind.ASSISTANT_INFERENCE: Authority.LOW,
        SourceKind.HYPOTHESIS: Authority.EPHEMERAL,
    },
    CredentialRole.HUMAN: {
        SourceKind.USER_STATEMENT: Authority.MEDIUM,
        SourceKind.USER_CORRECTION: Authority.HIGH,
    },
    CredentialRole.TOOL: {
        SourceKind.TOOL_OBSERVATION: Authority.HIGH,
        SourceKind.TEST_OUTPUT: Authority.HIGH,
    },
}


class ConflictDecision(StrEnum):
    CONTRADICTION = "contradiction"
    TEMPORAL_CHANGE = "temporal_change"
    DISMISSED = "dismissed"


class ClaimStatus(StrEnum):
    CANDIDATE = "candidate"
    ACTIVE = "active"
    VERIFIED = "verified"
    CONFLICTED = "conflicted"
    SUPERSEDED = "superseded"
    QUARANTINED = "quarantined"
    EXPIRED = "expired"
    EPHEMERAL = "ephemeral"
    DELETED = "deleted"


class RelationshipKind(StrEnum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    SUPERSEDES = "supersedes"
    DERIVED_FROM = "derived_from"
    RELATED_TO = "related_to"


class MemoryActionKind(StrEnum):
    CREATED = "created"
    STATUS_CHANGED = "status_changed"
    POSSIBLE_CONFLICT = "possible_conflict"
    DUPLICATE_DETECTED = "duplicate_detected"
    RELATIONSHIP_CREATED = "relationship_created"
    EXTRACTED = "extracted"


class ExtractionStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"


ALLOWED_TRANSITIONS = {
    ClaimStatus.CANDIDATE: {ClaimStatus.ACTIVE, ClaimStatus.QUARANTINED, ClaimStatus.EPHEMERAL, ClaimStatus.DELETED},
    ClaimStatus.ACTIVE: {ClaimStatus.VERIFIED, ClaimStatus.CONFLICTED, ClaimStatus.SUPERSEDED, ClaimStatus.EXPIRED, ClaimStatus.QUARANTINED, ClaimStatus.DELETED},
    ClaimStatus.VERIFIED: {ClaimStatus.CONFLICTED, ClaimStatus.SUPERSEDED, ClaimStatus.EXPIRED, ClaimStatus.QUARANTINED, ClaimStatus.DELETED},
    ClaimStatus.CONFLICTED: {ClaimStatus.ACTIVE, ClaimStatus.VERIFIED, ClaimStatus.SUPERSEDED, ClaimStatus.QUARANTINED, ClaimStatus.DELETED},
    ClaimStatus.QUARANTINED: {ClaimStatus.CANDIDATE, ClaimStatus.DELETED},
    ClaimStatus.EPHEMERAL: {ClaimStatus.CANDIDATE, ClaimStatus.EXPIRED, ClaimStatus.DELETED},
    ClaimStatus.EXPIRED: {ClaimStatus.ACTIVE, ClaimStatus.DELETED},
    ClaimStatus.SUPERSEDED: {ClaimStatus.ACTIVE, ClaimStatus.DELETED},
    ClaimStatus.DELETED: {ClaimStatus.CANDIDATE},
}
