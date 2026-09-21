import hashlib
import json
import secrets
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from sqlalchemy import String, cast, create_engine, func, or_, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, sessionmaker

from ..config import Settings
from ..core.domain import (
    ALLOWED_TRANSITIONS,
    SOURCE_AUTHORITY,
    ClaimStatus,
    ConflictDecision,
    CredentialRole,
    ExtractionStatus,
    MemoryActionKind,
    RelationshipKind,
    ScopeKind,
    SourceKind,
)
from ..memory.intelligence import (
    MemoryIntelligence,
    OllamaMemoryIntelligence,
    OpenAIMemoryIntelligence,
    claim_text,
)
from ..persistence.models import (
    Agent,
    Claim,
    ClaimEmbedding,
    ClaimRelationship,
    ConflictReview,
    Credential,
    Event,
    Evidence,
    ExtractionRun,
    MemoryAction,
    Organization,
    Project,
    RetrievalEvent,
    RetrievalItem,
    Scope,
    Session as AgentSession,
)
from .policies import actor, claim_view, overlap, require, require_human
from .operator_views import operator_claim_views
from .schemas import (
    ClaimIn,
    CredentialIn,
    EventIn,
    MemoryIn,
    NameIn,
    OrganizationIn,
    RelationshipIn,
    ReviewIn,
    ScopeIn,
    SessionIn,
    StatusIn,
)


def create_app(settings: Settings | None = None, intelligence: MemoryIntelligence | None = None) -> FastAPI:
    settings = settings or Settings()
    if intelligence is None:
        if settings.memory_provider == "ollama":
            intelligence = OllamaMemoryIntelligence(settings.ollama_base_url, settings.extraction_model, settings.embedding_model)
        elif settings.memory_provider == "openai" and settings.openai_api_key:
            intelligence = OpenAIMemoryIntelligence(settings.openai_api_key, settings.extraction_model, settings.embedding_model)
        elif settings.memory_provider not in {"ollama", "openai", "none"}:
            raise ValueError("MEMORY_PROVIDER must be ollama, openai, or none")
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    factory = sessionmaker(engine, expire_on_commit=False)
    app = FastAPI(title="Provena", version="0.1.2")

    def db_session():
        with factory() as db:
            try:
                yield db
                db.commit()
            except Exception:
                db.rollback()
                raise

    Db = Annotated[Session, Depends(db_session, scope="function")]

    def current_credential(db: Db, x_api_key: Annotated[str | None, Header()] = None) -> Credential:
        if not x_api_key:
            raise HTTPException(401, "API key required")
        digest = hashlib.sha256(x_api_key.encode()).hexdigest()
        row = db.scalar(select(Credential).where(Credential.key_hash == digest, Credential.revoked_at.is_(None)))
        if not row:
            raise HTTPException(401, "invalid API key")
        return row

    Principal = Annotated[Credential, Depends(current_credential)]

    def tenant(principal: Principal) -> UUID:
        return principal.organization_id

    Tenant = Annotated[UUID, Depends(tenant)]

    def check_bootstrap(token: str | None) -> None:
        if not settings.bootstrap_token or not token or not secrets.compare_digest(token, settings.bootstrap_token):
            raise HTTPException(403, "bootstrap unavailable")

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "provena"}

    @app.get("/ready")
    def ready(db: Db):
        db.execute(text("SELECT 1"))
        return {"status": "ready", "database": "reachable"}

    @app.post("/organizations", status_code=201)
    def create_organization(body: OrganizationIn, db: Db, x_bootstrap_token: Annotated[str | None, Header()] = None):
        check_bootstrap(x_bootstrap_token)
        key = secrets.token_urlsafe(32)
        row = Organization(name=body.name)
        db.add(row)
        db.flush()
        credential = Credential(organization_id=row.id, key_hash=hashlib.sha256(key.encode()).hexdigest(), role=CredentialRole.AGENT.value, label="initial agent key")
        db.add(credential)
        root = Scope(organization_id=row.id, kind=ScopeKind.ORGANIZATION.value, key="organization")
        db.add(root)
        db.flush()
        return {"id": row.id, "root_scope_id": root.id, "credential_id": credential.id, "api_key": key}

    @app.post("/organizations/{organization_id}/credentials", status_code=201)
    def issue_credential(organization_id: UUID, body: CredentialIn, db: Db, x_bootstrap_token: Annotated[str | None, Header()] = None):
        check_bootstrap(x_bootstrap_token)
        require(db.get(Organization, organization_id), "organization")
        key = secrets.token_urlsafe(32)
        row = Credential(organization_id=organization_id, key_hash=hashlib.sha256(key.encode()).hexdigest(), role=body.role.value, label=body.label)
        db.add(row)
        db.flush()
        return {"id": row.id, "role": row.role, "label": row.label, "api_key": key}

    @app.post("/organizations/{organization_id}/credentials/{credential_id}/rotate")
    def rotate_credential(organization_id: UUID, credential_id: UUID, db: Db, x_bootstrap_token: Annotated[str | None, Header()] = None):
        check_bootstrap(x_bootstrap_token)
        old = require(db.scalar(select(Credential).where(Credential.organization_id == organization_id, Credential.id == credential_id).with_for_update()), "credential")
        if old.revoked_at is not None:
            raise HTTPException(409, "credential already revoked")
        key = secrets.token_urlsafe(32)
        replacement = Credential(organization_id=organization_id, key_hash=hashlib.sha256(key.encode()).hexdigest(), role=old.role, label=old.label)
        db.add(replacement)
        db.flush()
        old.revoked_at = datetime.now(timezone.utc)
        db.flush()
        return {"id": replacement.id, "replaces": old.id, "role": replacement.role, "api_key": key}

    @app.post("/organizations/{organization_id}/credentials/{credential_id}/revoke")
    def revoke_credential(organization_id: UUID, credential_id: UUID, db: Db, x_bootstrap_token: Annotated[str | None, Header()] = None):
        check_bootstrap(x_bootstrap_token)
        row = require(db.scalar(select(Credential).where(Credential.organization_id == organization_id, Credential.id == credential_id).with_for_update()), "credential")
        if row.revoked_at is not None:
            raise HTTPException(409, "credential already revoked")
        row.revoked_at = datetime.now(timezone.utc)
        db.flush()
        return {"id": row.id, "revoked_at": row.revoked_at}

    @app.post("/projects", status_code=201)
    def create_project(body: NameIn, db: Db, org: Tenant):
        project = Project(organization_id=org, name=body.name)
        db.add(project)
        db.flush()
        root = require(db.scalar(select(Scope).where(Scope.organization_id == org, Scope.kind == ScopeKind.ORGANIZATION.value)), "root scope")
        scope = Scope(organization_id=org, project_id=project.id, parent_id=root.id, kind=ScopeKind.PROJECT.value, key=body.name)
        db.add(scope)
        db.flush()
        return {"id": project.id, "scope_id": scope.id}

    @app.post("/scopes", status_code=201)
    def create_scope(body: ScopeIn, db: Db, org: Tenant):
        if body.kind != ScopeKind.BRANCH:
            raise HTTPException(422, "only branch scopes can be created here")
        parent = require(db.scalar(select(Scope).where(Scope.organization_id == org, Scope.id == body.parent_id)), "parent scope")
        if parent.kind != ScopeKind.PROJECT.value or parent.project_id != body.project_id:
            raise HTTPException(422, "branch parent must be its project scope")
        row = Scope(organization_id=org, project_id=body.project_id, parent_id=parent.id, kind=body.kind.value, key=body.key)
        db.add(row)
        db.flush()
        return {"id": row.id, "kind": row.kind, "parent_id": row.parent_id}

    @app.post("/agents", status_code=201)
    def create_agent(body: NameIn, db: Db, org: Tenant):
        row = Agent(organization_id=org, name=body.name)
        db.add(row)
        db.flush()
        return {"id": row.id}

    @app.post("/sessions", status_code=201)
    def create_session(body: SessionIn, db: Db, org: Tenant):
        require(db.scalar(select(Scope).where(Scope.organization_id == org, Scope.id == body.scope_id)), "scope")
        if body.agent_id:
            require(db.scalar(select(Agent).where(Agent.organization_id == org, Agent.id == body.agent_id)), "agent")
        row = AgentSession(organization_id=org, scope_id=body.scope_id, agent_id=body.agent_id, external_ref=body.external_ref)
        db.add(row)
        db.flush()
        return {"id": row.id}

    @app.post("/events", status_code=201)
    def create_event(body: EventIn, db: Db, org: Tenant, principal: Principal):
        require(db.scalar(select(Scope).where(Scope.organization_id == org, Scope.id == body.scope_id)), "scope")
        if body.session_id:
            sess = require(db.scalar(select(AgentSession).where(AgentSession.organization_id == org, AgentSession.id == body.session_id)), "session")
            if sess.scope_id != body.scope_id:
                raise HTTPException(422, "event and session scope differ")
        if len(json.dumps(body.payload).encode()) > 65536:
            raise HTTPException(413, "event payload exceeds 64 KiB")
        authority = SOURCE_AUTHORITY[CredentialRole(principal.role)].get(body.source_kind)
        if authority is None:
            raise HTTPException(403, "source kind is not allowed for this credential")
        row = Event(organization_id=org, scope_id=body.scope_id, session_id=body.session_id, credential_id=principal.id, source_kind=body.source_kind.value, authority=authority.value, actor_ref=body.actor_ref, payload=body.payload)
        db.add(row)
        db.flush()
        return {"id": row.id, "recorded_at": row.recorded_at, "authority": row.authority}

    @app.get("/events/{event_id}")
    def get_event(event_id: UUID, db: Db, org: Tenant):
        row = require(db.scalar(select(Event).where(Event.organization_id == org, Event.id == event_id)), "event")
        return {"id": row.id, "scope_id": row.scope_id, "source_kind": row.source_kind, "authority": row.authority, "credential_id": row.credential_id, "actor_ref": row.actor_ref, "payload": row.payload, "recorded_at": row.recorded_at}

    @app.post("/claims", status_code=201)
    def create_claim(body: ClaimIn, db: Db, org: Tenant, principal: Principal):
        require(db.scalar(select(Scope).where(Scope.organization_id == org, Scope.id == body.scope_id)), "scope")
        events = db.scalars(select(Event).where(Event.organization_id == org, Event.id.in_(body.evidence_event_ids))).all()
        if len(events) != len(body.evidence_event_ids):
            raise HTTPException(404, "evidence event not found")
        if any(event.scope_id != body.scope_id for event in events):
            raise HTTPException(422, "evidence must have the claim scope")
        row = Claim(organization_id=org, scope_id=body.scope_id, subject=body.subject, predicate=body.predicate, value=body.value, status=ClaimStatus.CANDIDATE.value, valid_from=body.valid_from, valid_to=body.valid_to)
        db.add(row)
        db.flush()
        for event in events:
            db.add(Evidence(organization_id=org, claim_id=row.id, event_id=event.id))
        db.add(MemoryAction(organization_id=org, claim_id=row.id, action=MemoryActionKind.CREATED.value, version=0, new_status=row.status, reason="manual claim submission", actor_ref=actor(principal), credential_id=principal.id))
        db.flush()
        peers = db.scalars(select(Claim).where(Claim.organization_id == org, Claim.scope_id == row.scope_id, Claim.subject == row.subject, Claim.predicate == row.predicate, Claim.id != row.id, Claim.status != ClaimStatus.DELETED.value)).all()
        duplicate_ids = [p.id for p in peers if p.value == row.value and overlap(p, row)]
        possible_conflict_ids = [p.id for p in peers if p.value != row.value and overlap(p, row)]
        for peer_id in duplicate_ids:
            db.add(MemoryAction(organization_id=org, claim_id=row.id, action=MemoryActionKind.DUPLICATE_DETECTED.value, reason=f"same proposition and overlapping validity as claim {peer_id}", actor_ref="system"))
        for peer_id in possible_conflict_ids:
            reason = "same subject and predicate, different value, overlapping validity; requires review"
            db.add(ClaimRelationship(organization_id=org, from_claim_id=row.id, to_claim_id=peer_id, kind=RelationshipKind.RELATED_TO.value, reason=reason))
            db.add(MemoryAction(organization_id=org, claim_id=row.id, action=MemoryActionKind.POSSIBLE_CONFLICT.value, reason=f"{reason}: {peer_id}", actor_ref="system"))
        return {**claim_view(row), "duplicate_of": duplicate_ids, "possible_conflicts": possible_conflict_ids}

    @app.post("/memories", status_code=201)
    def record_memory(body: MemoryIn, db: Db, org: Tenant, principal: Principal):
        """Atomically preserve a turn and its optional candidate proposition."""
        session_id = body.session_id
        if body.session_external_ref is not None:
            session_id = db.scalar(
                insert(AgentSession)
                .values(organization_id=org, scope_id=body.scope_id, external_ref=body.session_external_ref)
                .on_conflict_do_nothing(constraint="uq_session_external_ref")
                .returning(AgentSession.id)
            )
            if session_id is None:
                session_id = db.scalar(select(AgentSession.id).where(AgentSession.organization_id == org, AgentSession.scope_id == body.scope_id, AgentSession.external_ref == body.session_external_ref))
        event = create_event(EventIn(scope_id=body.scope_id, session_id=session_id, source_kind=body.source_kind, actor_ref=body.actor_ref, payload={"text": body.text}), db, org, principal)
        claim = None
        if body.proposition is not None:
            proposal = body.proposition
            claim = create_claim(ClaimIn(scope_id=body.scope_id, subject=proposal.subject, predicate=proposal.predicate, value=proposal.value, evidence_event_ids=[event["id"]], valid_from=proposal.valid_from, valid_to=proposal.valid_to), db, org, principal)
        return {"event": event, "claim": claim, "scope_id": body.scope_id, "session_id": session_id, "source_kind": body.source_kind}

    @app.post("/events/{event_id}/extract", status_code=201)
    def extract_event(event_id: UUID, db: Db, org: Tenant, principal: Principal):
        event = require(db.scalar(select(Event).where(Event.organization_id == org, Event.id == event_id).with_for_update()), "event")
        if intelligence is None:
            return {"status": "failed", "error": "memory intelligence is not configured", "claims": []}
        existing = db.scalar(select(ExtractionRun).where(ExtractionRun.organization_id == org, ExtractionRun.event_id == event.id, ExtractionRun.extractor_model == intelligence.extraction_model, ExtractionRun.embedding_model == intelligence.embedding_model, ExtractionRun.status == ExtractionStatus.COMPLETED.value).order_by(ExtractionRun.created_at.desc()))
        if existing:
            claim_ids = db.scalars(select(Evidence.claim_id).where(Evidence.organization_id == org, Evidence.event_id == event.id)).all()
            return {"id": existing.id, "status": existing.status, "facts": existing.facts, "claim_ids": claim_ids, "reused": True}
        try:
            facts = intelligence.extract(event.payload.get("text", ""), event.source_kind)
            embeddings = intelligence.embed([claim_text(f.subject, f.predicate, f.value) for f in facts])
            claims = []
            fact_views = []
            with db.begin_nested():
                for fact, embedding in zip(facts, embeddings, strict=True):
                    created = create_claim(ClaimIn(scope_id=event.scope_id, subject=fact.subject, predicate=fact.predicate, value=fact.value, evidence_event_ids=[event.id]), db, org, principal)
                    db.add(ClaimEmbedding(organization_id=org, claim_id=created["id"], model=intelligence.embedding_model, embedding=embedding))
                    db.add(MemoryAction(organization_id=org, claim_id=created["id"], action=MemoryActionKind.EXTRACTED.value, reason=f"extracted by {intelligence.extraction_model} with confidence {fact.confidence}", actor_ref="system:extractor"))
                    claims.append(created)
                    fact_views.append({**fact.model_dump(), "claim_id": str(created["id"])})
                run = ExtractionRun(organization_id=org, event_id=event.id, extractor_model=intelligence.extraction_model, embedding_model=intelligence.embedding_model, status=ExtractionStatus.COMPLETED.value, facts=fact_views)
                db.add(run)
                db.flush()
            return {"id": run.id, "status": run.status, "facts": fact_views, "claims": claims, "reused": False}
        except Exception as exc:
            run = ExtractionRun(organization_id=org, event_id=event.id, extractor_model=intelligence.extraction_model, embedding_model=intelligence.embedding_model, status=ExtractionStatus.FAILED.value, facts=[], error=str(exc)[:2000])
            db.add(run)
            db.flush()
            return {"id": run.id, "status": run.status, "error": run.error, "claims": [], "reused": False}

    @app.get("/claims/{claim_id}")
    def get_claim(claim_id: UUID, db: Db, org: Tenant):
        return claim_view(require(db.scalar(select(Claim).where(Claim.organization_id == org, Claim.id == claim_id)), "claim"))

    @app.post("/claims/{claim_id}/status")
    def change_status(claim_id: UUID, body: StatusIn, db: Db, org: Tenant, principal: Principal):
        require_human(principal)
        row = require(db.scalar(select(Claim).where(Claim.organization_id == org, Claim.id == claim_id).with_for_update()), "claim")
        current = ClaimStatus(row.status)
        if body.status not in ALLOWED_TRANSITIONS[current]:
            raise HTTPException(409, "invalid status transition")
        next_version = row.status_version + 1
        action = MemoryAction(organization_id=org, claim_id=row.id, action=MemoryActionKind.STATUS_CHANGED.value, version=next_version, old_status=current.value, new_status=body.status.value, reason=body.reason, actor_ref=actor(principal), credential_id=principal.id)
        db.add(action)
        db.flush()
        row.status = body.status.value
        row.status_version = next_version
        db.flush()
        return claim_view(row)

    @app.post("/relationships", status_code=201)
    def create_relationship(body: RelationshipIn, db: Db, org: Tenant, principal: Principal):
        require_human(principal)
        if body.kind == RelationshipKind.RELATED_TO:
            raise HTTPException(422, "related_to is reserved for system-detected possible conflicts")
        if body.from_claim_id == body.to_claim_id:
            raise HTTPException(422, "relationship requires distinct claims")
        claims = db.scalars(select(Claim).where(Claim.organization_id == org, Claim.id.in_([body.from_claim_id, body.to_claim_id]))).all()
        if len(claims) != 2:
            raise HTTPException(404, "claim not found")
        by_id = {c.id: c for c in claims}
        if by_id[body.from_claim_id].scope_id != by_id[body.to_claim_id].scope_id:
            raise HTTPException(422, "relationship requires one scope")
        row = ClaimRelationship(organization_id=org, from_claim_id=body.from_claim_id, to_claim_id=body.to_claim_id, kind=body.kind.value, reason=body.reason)
        db.add(row)
        db.add(MemoryAction(organization_id=org, claim_id=body.from_claim_id, action=MemoryActionKind.RELATIONSHIP_CREATED.value, reason=f"{body.kind.value} {body.to_claim_id}: {body.reason}", actor_ref=actor(principal), credential_id=principal.id))
        db.flush()
        return {"id": row.id, "kind": row.kind}

    @app.get("/conflicts")
    def list_conflicts(scope_id: UUID, db: Db, org: Tenant):
        require(db.scalar(select(Scope).where(Scope.organization_id == org, Scope.id == scope_id)), "scope")
        reviewed = select(ConflictReview.id).where(ConflictReview.organization_id == ClaimRelationship.organization_id, ConflictReview.case_relationship_id == ClaimRelationship.id).exists()
        cases = db.scalars(select(ClaimRelationship).join(Claim, (ClaimRelationship.organization_id == Claim.organization_id) & (ClaimRelationship.from_claim_id == Claim.id)).where(ClaimRelationship.organization_id == org, ClaimRelationship.kind == RelationshipKind.RELATED_TO.value, Claim.scope_id == scope_id, ~reviewed).order_by(ClaimRelationship.created_at, ClaimRelationship.id).limit(100)).all()
        if not cases:
            return {"cases": []}
        claim_ids = {claim_id for case in cases for claim_id in (case.from_claim_id, case.to_claim_id)}
        claims = db.scalars(select(Claim).where(Claim.organization_id == org, Claim.id.in_(claim_ids))).all()
        views = {claim["id"]: claim for claim in operator_claim_views(db, org, claims)}
        return {"cases": [{"id": case.id, "from_claim_id": case.from_claim_id, "to_claim_id": case.to_claim_id, "from_claim": views[case.from_claim_id], "to_claim": views[case.to_claim_id], "reason": case.reason, "created_at": case.created_at} for case in cases]}

    @app.post("/conflicts/{case_id}/review")
    def review_conflict(case_id: UUID, body: ReviewIn, db: Db, org: Tenant, principal: Principal):
        require_human(principal)
        case = require(db.scalar(select(ClaimRelationship).where(ClaimRelationship.organization_id == org, ClaimRelationship.id == case_id, ClaimRelationship.kind == RelationshipKind.RELATED_TO.value).with_for_update()), "possible conflict")
        if db.scalar(select(ConflictReview.id).where(ConflictReview.organization_id == org, ConflictReview.case_relationship_id == case.id)):
            raise HTTPException(409, "possible conflict already reviewed")
        if body.superseding_claim_id and body.superseding_claim_id not in (case.from_claim_id, case.to_claim_id):
            raise HTTPException(422, "superseding claim must be one of the case claims")
        review = ConflictReview(organization_id=org, case_relationship_id=case.id, reviewer_credential_id=principal.id, decision=body.decision.value, reason=body.reason, superseding_claim_id=body.superseding_claim_id)
        db.add(review)
        relation_kind = {ConflictDecision.CONTRADICTION: RelationshipKind.CONTRADICTS, ConflictDecision.TEMPORAL_CHANGE: RelationshipKind.SUPERSEDES}.get(body.decision)
        if relation_kind:
            from_id = body.superseding_claim_id or case.from_claim_id
            to_id = case.to_claim_id if from_id == case.from_claim_id else case.from_claim_id
            existing = db.scalar(select(ClaimRelationship).where(ClaimRelationship.organization_id == org, ClaimRelationship.from_claim_id == from_id, ClaimRelationship.to_claim_id == to_id, ClaimRelationship.kind == relation_kind.value))
            if not existing:
                db.add(ClaimRelationship(organization_id=org, from_claim_id=from_id, to_claim_id=to_id, kind=relation_kind.value, reason=body.reason))
                db.add(MemoryAction(organization_id=org, claim_id=from_id, action=MemoryActionKind.RELATIONSHIP_CREATED.value, reason=f"reviewed {relation_kind.value} {to_id}: {body.reason}", actor_ref=actor(principal), credential_id=principal.id))
        db.flush()
        return {"id": review.id, "case_relationship_id": case.id, "decision": review.decision, "superseding_claim_id": review.superseding_claim_id, "reviewer_credential_id": principal.id}

    @app.get("/claims")
    def retrieve_claims(scope_id: UUID, db: Db, org: Tenant, principal: Principal, predicate: str | None = None, q: str | None = Query(default=None, min_length=1, max_length=2000), limit: int = Query(default=50, ge=1, le=100)):
        require(db.scalar(select(Scope).where(Scope.organization_id == org, Scope.id == scope_id)), "scope")
        eligible = [ClaimStatus.CANDIDATE.value, ClaimStatus.ACTIVE.value, ClaimStatus.VERIFIED.value, ClaimStatus.CONFLICTED.value]
        query = select(Claim).where(Claim.organization_id == org, Claim.scope_id == scope_id, Claim.status.in_(eligible))
        if predicate:
            query = query.where(Claim.predicate == predicate)
        method = "exact"
        if q:
            if intelligence is None:
                raise HTTPException(503, "semantic retrieval is not configured")
            vector = intelligence.embed([q])[0]
            query = query.join(ClaimEmbedding, (ClaimEmbedding.organization_id == Claim.organization_id) & (ClaimEmbedding.claim_id == Claim.id)).where(ClaimEmbedding.model == intelligence.embedding_model, ClaimEmbedding.dimensions == len(vector)).order_by(ClaimEmbedding.embedding.cosine_distance(vector), Claim.recorded_at.desc())
            method = "semantic"
        else:
            query = query.order_by(Claim.recorded_at.desc(), Claim.id)
        rows = db.scalars(query.limit(limit)).all()
        retrieval = RetrievalEvent(organization_id=org, scope_id=scope_id, predicate=predicate, query_text=q, method=method, actor_ref=actor(principal))
        db.add(retrieval)
        db.flush()
        for row in rows:
            db.add(RetrievalItem(organization_id=org, retrieval_id=retrieval.id, claim_id=row.id))
        sources: dict[UUID, list[dict]] = {row.id: [] for row in rows}
        if rows:
            evidence_rows = db.execute(select(Evidence, Event).join(Event, (Evidence.organization_id == Event.organization_id) & (Evidence.event_id == Event.id)).where(Evidence.organization_id == org, Evidence.claim_id.in_([row.id for row in rows]))).all()
            for evidence, event in evidence_rows:
                sources[evidence.claim_id].append({"event_id": event.id, "source_kind": event.source_kind, "authority": event.authority})
        return {"retrieval_id": retrieval.id, "claims": [{**claim_view(row), "sources": sources[row.id]} for row in rows]}

    @app.get("/claims/{claim_id}/explain")
    def explain(claim_id: UUID, db: Db, org: Tenant):
        row = require(db.scalar(select(Claim).where(Claim.organization_id == org, Claim.id == claim_id)), "claim")
        evidence_rows = db.execute(select(Evidence, Event).join(Event, (Evidence.organization_id == Event.organization_id) & (Evidence.event_id == Event.id)).where(Evidence.organization_id == org, Evidence.claim_id == claim_id)).all()
        credential_ids = {event.credential_id for _, event in evidence_rows if event.credential_id is not None}
        credentials = {credential.id: credential for credential in db.scalars(select(Credential).where(Credential.organization_id == org, Credential.id.in_(credential_ids))).all()} if credential_ids else {}
        relations = db.scalars(select(ClaimRelationship).where(ClaimRelationship.organization_id == org, (ClaimRelationship.from_claim_id == claim_id) | (ClaimRelationship.to_claim_id == claim_id))).all()
        actions = db.scalars(select(MemoryAction).where(MemoryAction.organization_id == org, MemoryAction.claim_id == claim_id).order_by(MemoryAction.created_at, MemoryAction.id)).all()
        retrievals = db.scalars(select(RetrievalEvent).join(RetrievalItem, (RetrievalItem.organization_id == RetrievalEvent.organization_id) & (RetrievalItem.retrieval_id == RetrievalEvent.id)).where(RetrievalItem.organization_id == org, RetrievalItem.claim_id == claim_id).order_by(RetrievalEvent.created_at)).all()
        reviews = db.scalars(select(ConflictReview).join(ClaimRelationship, (ConflictReview.organization_id == ClaimRelationship.organization_id) & (ConflictReview.case_relationship_id == ClaimRelationship.id)).where(ConflictReview.organization_id == org, (ClaimRelationship.from_claim_id == claim_id) | (ClaimRelationship.to_claim_id == claim_id))).all()
        evidence_event_ids = [event.id for _, event in evidence_rows]
        extraction_runs = db.scalars(select(ExtractionRun).where(ExtractionRun.organization_id == org, ExtractionRun.event_id.in_(evidence_event_ids)).order_by(ExtractionRun.created_at, ExtractionRun.id)).all() if evidence_event_ids else []
        evidence_view = []
        for evidence, event in evidence_rows:
            credential = credentials.get(event.credential_id)
            evidence_view.append({
                "id": evidence.id,
                "event": {
                    "id": event.id,
                    "source_kind": event.source_kind,
                    "authority": event.authority,
                    "credential_id": event.credential_id,
                    "credential": {
                        "role": credential.role,
                        "label": credential.label,
                        "revoked_at": credential.revoked_at,
                    } if credential else None,
                    "actor_ref": event.actor_ref,
                    "payload": event.payload,
                    "recorded_at": event.recorded_at,
                },
            })
        return {
            "claim": claim_view(row),
            "evidence": evidence_view,
            "relationships": [{"id": relation.id, "kind": relation.kind, "from_claim_id": relation.from_claim_id, "to_claim_id": relation.to_claim_id, "reason": relation.reason} for relation in relations],
            "conflict_reviews": [{"case_relationship_id": review.case_relationship_id, "decision": review.decision, "superseding_claim_id": review.superseding_claim_id, "reason": review.reason, "reviewer_credential_id": review.reviewer_credential_id, "created_at": review.created_at} for review in reviews],
            "actions": [{"action": action.action, "old_status": action.old_status, "new_status": action.new_status, "reason": action.reason, "actor_ref": action.actor_ref, "credential_id": action.credential_id, "created_at": action.created_at} for action in actions],
            "extractions": [{"id": run.id, "event_id": run.event_id, "extractor_model": run.extractor_model, "embedding_model": run.embedding_model, "status": run.status, "facts": run.facts, "error": run.error, "created_at": run.created_at} for run in extraction_runs],
            "retrievals": [{"id": retrieval.id, "created_at": retrieval.created_at} for retrieval in retrievals],
            "action_influence": "not_tracked",
        }

    @app.get("/operator/context")
    def operator_context(db: Db, org: Tenant, principal: Principal, scope_id: UUID | None = None):
        organization = require(db.scalar(select(Organization).where(Organization.id == org)), "organization")
        if scope_id is not None:
            require(db.scalar(select(Scope).where(Scope.organization_id == org, Scope.id == scope_id)), "scope")
        projects = db.scalars(select(Project).where(Project.organization_id == org).order_by(Project.name, Project.id)).all()
        scopes = db.scalars(select(Scope).where(Scope.organization_id == org).order_by(Scope.created_at, Scope.id)).all()
        return {
            "organization": {"id": organization.id, "name": organization.name},
            "principal": {"id": principal.id, "role": principal.role, "label": principal.label},
            "selected_scope_id": scope_id,
            "projects": [{"id": row.id, "name": row.name, "created_at": row.created_at} for row in projects],
            "scopes": [{"id": row.id, "project_id": row.project_id, "parent_id": row.parent_id, "kind": row.kind, "key": row.key, "created_at": row.created_at} for row in scopes],
        }

    @app.get("/operator/claims")
    def operator_claims(
        scope_id: UUID,
        db: Db,
        org: Tenant,
        status: list[ClaimStatus] = Query(default=[]),
        q: str | None = Query(default=None, min_length=1, max_length=500),
        page: int = Query(default=1, ge=1),
        page_size: int = Query(default=25, ge=1, le=100),
    ):
        require(db.scalar(select(Scope).where(Scope.organization_id == org, Scope.id == scope_id)), "scope")
        filters = [Claim.organization_id == org, Claim.scope_id == scope_id]
        if status:
            filters.append(Claim.status.in_([item.value for item in status]))
        if q:
            pattern = f"%{q}%"
            filters.append(or_(Claim.subject.ilike(pattern), Claim.predicate.ilike(pattern), cast(Claim.value, String).ilike(pattern)))
        total = db.scalar(select(func.count()).select_from(Claim).where(*filters)) or 0
        rows = db.scalars(
            select(Claim)
            .where(*filters)
            .order_by(Claim.recorded_at.desc(), Claim.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        status_rows = db.execute(
            select(Claim.status, func.count())
            .where(Claim.organization_id == org, Claim.scope_id == scope_id)
            .group_by(Claim.status)
        ).all()
        return {
            "items": operator_claim_views(db, org, rows),
            "page": page,
            "page_size": page_size,
            "total": total,
            "status_counts": {name: count for name, count in status_rows},
        }

    @app.get("/operator/review-queue")
    def operator_review_queue(
        scope_id: UUID,
        db: Db,
        org: Tenant,
        page: int = Query(default=1, ge=1),
        page_size: int = Query(default=50, ge=1, le=100),
    ):
        require(db.scalar(select(Scope).where(Scope.organization_id == org, Scope.id == scope_id)), "scope")
        total = db.scalar(select(func.count()).select_from(Claim).where(Claim.organization_id == org, Claim.scope_id == scope_id, Claim.status == ClaimStatus.CANDIDATE.value)) or 0
        rows = db.scalars(
            select(Claim)
            .where(Claim.organization_id == org, Claim.scope_id == scope_id, Claim.status == ClaimStatus.CANDIDATE.value)
            .order_by(Claim.recorded_at, Claim.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        reviewed = select(ConflictReview.id).where(
            ConflictReview.organization_id == ClaimRelationship.organization_id,
            ConflictReview.case_relationship_id == ClaimRelationship.id,
        ).exists()
        conflict_count = db.scalar(
            select(func.count()).select_from(ClaimRelationship)
            .join(Claim, (ClaimRelationship.organization_id == Claim.organization_id) & (ClaimRelationship.from_claim_id == Claim.id))
            .where(ClaimRelationship.organization_id == org, ClaimRelationship.kind == RelationshipKind.RELATED_TO.value, Claim.scope_id == scope_id, ~reviewed)
        ) or 0
        quarantined = db.scalar(select(func.count()).select_from(Claim).where(Claim.organization_id == org, Claim.scope_id == scope_id, Claim.status == ClaimStatus.QUARANTINED.value)) or 0
        failed = db.scalar(
            select(func.count()).select_from(ExtractionRun)
            .join(Event, (ExtractionRun.organization_id == Event.organization_id) & (ExtractionRun.event_id == Event.id))
            .where(ExtractionRun.organization_id == org, Event.scope_id == scope_id, ExtractionRun.status == ExtractionStatus.FAILED.value)
        ) or 0
        return {
            "items": operator_claim_views(db, org, rows),
            "page": page,
            "page_size": page_size,
            "total": total,
            "metrics": {"candidate": total, "conflicted": conflict_count, "quarantined": quarantined, "failed_extraction": failed},
        }

    @app.get("/operator/scopes")
    def operator_scopes(db: Db, org: Tenant):
        organization = require(db.scalar(select(Organization).where(Organization.id == org)), "organization")
        projects = {row.id: row for row in db.scalars(select(Project).where(Project.organization_id == org)).all()}
        scopes = db.scalars(select(Scope).where(Scope.organization_id == org).order_by(Scope.created_at, Scope.id)).all()
        count_rows = db.execute(
            select(Claim.scope_id, Claim.status, func.count()).where(Claim.organization_id == org).group_by(Claim.scope_id, Claim.status)
        ).all()
        counts: dict[UUID, dict[str, int]] = {}
        for current_scope_id, current_status, count in count_rows:
            counts.setdefault(current_scope_id, {})[current_status] = count
        sessions = db.execute(
            select(AgentSession.scope_id, Agent.id, Agent.name, func.count(AgentSession.id), func.max(AgentSession.created_at))
            .join(Agent, (AgentSession.organization_id == Agent.organization_id) & (AgentSession.agent_id == Agent.id))
            .where(AgentSession.organization_id == org)
            .group_by(AgentSession.scope_id, Agent.id, Agent.name)
        ).all()
        agents_by_scope: dict[UUID, list[dict]] = {}
        for current_scope_id, agent_id, name, session_count, last_active in sessions:
            agents_by_scope.setdefault(current_scope_id, []).append({"id": agent_id, "name": name, "session_count": session_count, "last_active": last_active})
        return {
            "organization": {"id": organization.id, "name": organization.name},
            "items": [{
                "id": row.id,
                "project_id": row.project_id,
                "project_name": projects[row.project_id].name if row.project_id in projects else None,
                "parent_id": row.parent_id,
                "kind": row.kind,
                "key": row.key,
                "created_at": row.created_at,
                "claim_counts": counts.get(row.id, {}),
                "claim_total": sum(counts.get(row.id, {}).values()),
                "agents": agents_by_scope.get(row.id, []),
            } for row in scopes],
        }

    @app.get("/operator/retrievals")
    def operator_retrievals(scope_id: UUID, db: Db, org: Tenant, limit: int = Query(default=50, ge=1, le=100)):
        require(db.scalar(select(Scope).where(Scope.organization_id == org, Scope.id == scope_id)), "scope")
        rows = db.execute(
            select(RetrievalEvent, func.count(RetrievalItem.claim_id))
            .outerjoin(RetrievalItem, (RetrievalItem.organization_id == RetrievalEvent.organization_id) & (RetrievalItem.retrieval_id == RetrievalEvent.id))
            .where(RetrievalEvent.organization_id == org, RetrievalEvent.scope_id == scope_id)
            .group_by(RetrievalEvent.id)
            .order_by(RetrievalEvent.created_at.desc(), RetrievalEvent.id.desc())
            .limit(limit)
        ).all()
        return {"items": [{"id": row.id, "scope_id": row.scope_id, "predicate": row.predicate, "query_text": row.query_text, "method": row.method, "actor_ref": row.actor_ref, "created_at": row.created_at, "claim_count": count} for row, count in rows]}

    @app.get("/operator/retrievals/{retrieval_id}")
    def operator_retrieval_detail(retrieval_id: UUID, db: Db, org: Tenant):
        retrieval = require(db.scalar(select(RetrievalEvent).where(RetrievalEvent.organization_id == org, RetrievalEvent.id == retrieval_id)), "retrieval")
        claim_rows = db.scalars(
            select(Claim)
            .join(RetrievalItem, (RetrievalItem.organization_id == Claim.organization_id) & (RetrievalItem.claim_id == Claim.id))
            .where(RetrievalItem.organization_id == org, RetrievalItem.retrieval_id == retrieval.id)
            .order_by(Claim.recorded_at.desc(), Claim.id.desc())
        ).all()
        return {
            "retrieval": {"id": retrieval.id, "scope_id": retrieval.scope_id, "predicate": retrieval.predicate, "query_text": retrieval.query_text, "method": retrieval.method, "actor_ref": retrieval.actor_ref, "created_at": retrieval.created_at},
            "claims": operator_claim_views(db, org, claim_rows),
            "similarity_scores": "not_recorded",
            "filtering_diagnostics": "not_recorded",
        }

    @app.get("/operator/integrations")
    def operator_integrations(db: Db, org: Tenant):
        credentials = db.scalars(select(Credential).where(Credential.organization_id == org).order_by(Credential.created_at.desc(), Credential.id.desc())).all()
        agents = db.scalars(select(Agent).where(Agent.organization_id == org).order_by(Agent.name, Agent.id)).all()
        sessions = db.execute(
            select(AgentSession.agent_id, func.count(AgentSession.id), func.max(AgentSession.created_at))
            .where(AgentSession.organization_id == org)
            .group_by(AgentSession.agent_id)
        ).all()
        activity = {agent_id: {"session_count": count, "last_active": last_active} for agent_id, count, last_active in sessions if agent_id}
        extractions = db.scalars(select(ExtractionRun).where(ExtractionRun.organization_id == org).order_by(ExtractionRun.created_at.desc()).limit(20)).all()
        return {
            "credentials": [{"id": row.id, "role": row.role, "label": row.label, "created_at": row.created_at, "revoked_at": row.revoked_at} for row in credentials],
            "agents": [{"id": row.id, "name": row.name, "created_at": row.created_at, **activity.get(row.id, {"session_count": 0, "last_active": None})} for row in agents],
            "extractions": [{"id": row.id, "extractor_model": row.extractor_model, "embedding_model": row.embedding_model, "status": row.status, "error": row.error, "created_at": row.created_at} for row in extractions],
            "raw_keys_exposed": False,
        }

    @app.get("/operator/audit")
    def operator_audit(scope_id: UUID, db: Db, org: Tenant, limit: int = Query(default=100, ge=1, le=200)):
        require(db.scalar(select(Scope).where(Scope.organization_id == org, Scope.id == scope_id)), "scope")
        rows = db.scalars(
            select(MemoryAction)
            .join(Claim, (MemoryAction.organization_id == Claim.organization_id) & (MemoryAction.claim_id == Claim.id))
            .where(MemoryAction.organization_id == org, Claim.scope_id == scope_id)
            .order_by(MemoryAction.created_at.desc(), MemoryAction.id.desc())
            .limit(limit)
        ).all()
        return {"items": [{"id": row.id, "claim_id": row.claim_id, "action": row.action, "version": row.version, "old_status": row.old_status, "new_status": row.new_status, "reason": row.reason, "actor_ref": row.actor_ref, "credential_id": row.credential_id, "created_at": row.created_at} for row in rows]}

    @app.get("/operator/overview")
    def operator_overview(scope_id: UUID, db: Db, org: Tenant):
        require(db.scalar(select(Scope).where(Scope.organization_id == org, Scope.id == scope_id)), "scope")
        status_rows = db.execute(select(Claim.status, func.count()).where(Claim.organization_id == org, Claim.scope_id == scope_id).group_by(Claim.status)).all()
        retrieval_count = db.scalar(select(func.count()).select_from(RetrievalEvent).where(RetrievalEvent.organization_id == org, RetrievalEvent.scope_id == scope_id)) or 0
        event_count = db.scalar(select(func.count()).select_from(Event).where(Event.organization_id == org, Event.scope_id == scope_id)) or 0
        failed_extractions = db.scalar(
            select(func.count()).select_from(ExtractionRun)
            .join(Event, (ExtractionRun.organization_id == Event.organization_id) & (ExtractionRun.event_id == Event.id))
            .where(ExtractionRun.organization_id == org, Event.scope_id == scope_id, ExtractionRun.status == ExtractionStatus.FAILED.value)
        ) or 0
        return {"status_counts": {name: count for name, count in status_rows}, "retrieval_count": retrieval_count, "event_count": event_count, "failed_extraction_count": failed_extractions}

    return app


app = create_app()
