import json
from collections import defaultdict
from typing import Iterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..persistence.models import Claim, ClaimRelationship, Credential, Event, Evidence, ExtractionRun
from .policies import claim_view


AUTHORITY_RANK = {"ephemeral": 0, "low": 1, "medium": 2, "high": 3}


def _claim_id_from_fact(fact: object) -> UUID | None:
    if not isinstance(fact, dict) or not fact.get("claim_id"):
        return None
    try:
        return UUID(str(fact["claim_id"]))
    except (TypeError, ValueError):
        return None


def _confidence_from_fact(fact: object) -> float | None:
    if not isinstance(fact, dict):
        return None
    value = fact.get("confidence")
    if not isinstance(value, (int, float)):
        return None
    return max(0.0, min(float(value), 1.0))


def operator_claim_views(db: Session, organization_id: UUID, claims: Iterable[Claim]) -> list[dict]:
    """Build a truthful console projection without mutating retrieval history."""
    rows = list(claims)
    if not rows:
        return []

    claim_ids = [row.id for row in rows]
    evidence_rows = db.execute(
        select(Evidence, Event)
        .join(Event, (Evidence.organization_id == Event.organization_id) & (Evidence.event_id == Event.id))
        .where(Evidence.organization_id == organization_id, Evidence.claim_id.in_(claim_ids))
        .order_by(Event.recorded_at, Event.id)
    ).all()

    credential_ids = {event.credential_id for _, event in evidence_rows if event.credential_id}
    credentials = {
        row.id: row
        for row in db.scalars(
            select(Credential).where(
                Credential.organization_id == organization_id,
                Credential.id.in_(credential_ids),
            )
        ).all()
    } if credential_ids else {}

    sources: dict[UUID, list[dict]] = defaultdict(list)
    event_ids: set[UUID] = set()
    for evidence, event in evidence_rows:
        event_ids.add(event.id)
        credential = credentials.get(event.credential_id)
        sources[evidence.claim_id].append({
            "evidence_id": evidence.id,
            "event_id": event.id,
            "session_id": event.session_id,
            "source_kind": event.source_kind,
            "authority": event.authority,
            "actor_ref": event.actor_ref,
            "payload": event.payload,
            "recorded_at": event.recorded_at,
            "credential": {
                "id": credential.id,
                "role": credential.role,
                "label": credential.label,
                "revoked_at": credential.revoked_at,
            } if credential else None,
        })

    confidence: dict[UUID, float] = {}
    extraction: dict[UUID, dict] = {}
    if event_ids:
        runs = db.scalars(
            select(ExtractionRun)
            .where(ExtractionRun.organization_id == organization_id, ExtractionRun.event_id.in_(event_ids))
            .order_by(ExtractionRun.created_at.desc(), ExtractionRun.id.desc())
        ).all()
        for run in runs:
            for fact in run.facts:
                claim_id = _claim_id_from_fact(fact)
                if claim_id not in claim_ids or claim_id in extraction:
                    continue
                extraction[claim_id] = {
                    "id": run.id,
                    "event_id": run.event_id,
                    "extractor_model": run.extractor_model,
                    "embedding_model": run.embedding_model,
                    "status": run.status,
                    "error": run.error,
                    "created_at": run.created_at,
                }
                value = _confidence_from_fact(fact)
                if value is not None:
                    confidence[claim_id] = value

    relationships: dict[UUID, list[dict]] = defaultdict(list)
    relation_rows = db.scalars(
        select(ClaimRelationship).where(
            ClaimRelationship.organization_id == organization_id,
            (ClaimRelationship.from_claim_id.in_(claim_ids)) | (ClaimRelationship.to_claim_id.in_(claim_ids)),
        )
    ).all()
    for relation in relation_rows:
        view = {
            "id": relation.id,
            "kind": relation.kind,
            "from_claim_id": relation.from_claim_id,
            "to_claim_id": relation.to_claim_id,
            "reason": relation.reason,
            "created_at": relation.created_at,
        }
        if relation.from_claim_id in claim_ids:
            relationships[relation.from_claim_id].append(view)
        if relation.to_claim_id in claim_ids:
            relationships[relation.to_claim_id].append(view)

    result = []
    for row in rows:
        claim_sources = sources[row.id]
        authority = max(
            (source["authority"] for source in claim_sources),
            key=lambda value: AUTHORITY_RANK.get(value, -1),
            default=None,
        )
        result.append({
            **claim_view(row),
            "statement": f"{row.subject}.{row.predicate} = {json.dumps(row.value, sort_keys=True, separators=(',', ':'))}",
            "authority": authority,
            "confidence": confidence.get(row.id),
            "sources": claim_sources,
            "evidence_count": len(claim_sources),
            "extraction": extraction.get(row.id),
            "relationships": relationships[row.id],
            "risk_flags": [],
            "risk_assessment": "not_recorded",
        })
    return result
