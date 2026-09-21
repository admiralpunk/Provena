from fastapi import HTTPException

from ..core.domain import CredentialRole
from ..persistence.models import Claim, Credential


def require(row, what: str):
    if row is None:
        raise HTTPException(404, f"{what} not found")
    return row


def overlap(a: Claim, b: Claim) -> bool:
    return (a.valid_to is None or b.valid_from is None or a.valid_to > b.valid_from) and (
        b.valid_to is None or a.valid_from is None or b.valid_to > a.valid_from
    )


def claim_view(row: Claim) -> dict:
    return {
        "id": row.id,
        "scope_id": row.scope_id,
        "subject": row.subject,
        "predicate": row.predicate,
        "value": row.value,
        "status": row.status,
        "status_version": row.status_version,
        "valid_from": row.valid_from,
        "valid_to": row.valid_to,
        "recorded_at": row.recorded_at,
    }


def actor(principal: Credential) -> str:
    return f"credential:{principal.id}"


def require_human(principal: Credential) -> None:
    if principal.role != CredentialRole.HUMAN.value:
        raise HTTPException(403, "human review credential required")
