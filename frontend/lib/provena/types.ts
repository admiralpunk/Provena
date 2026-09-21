export type ClaimStatus = "candidate" | "active" | "verified" | "conflicted" | "superseded" | "quarantined" | "expired" | "ephemeral" | "deleted";
export type Authority = "high" | "medium" | "low" | "ephemeral" | null;

export type SourceEvidence = {
  evidence_id: string;
  event_id: string;
  session_id: string | null;
  source_kind: string;
  authority: Exclude<Authority, null>;
  actor_ref: string | null;
  payload: Record<string, unknown>;
  recorded_at: string;
  credential: { id: string; role: string; label: string; revoked_at: string | null } | null;
};

export type ClaimRelationship = {
  id: string;
  kind: string;
  from_claim_id: string;
  to_claim_id: string;
  reason: string;
  created_at?: string;
};

export type OperatorClaim = {
  id: string;
  scope_id: string;
  subject: string;
  predicate: string;
  value: Record<string, unknown>;
  status: ClaimStatus;
  status_version: number;
  valid_from: string | null;
  valid_to: string | null;
  recorded_at: string;
  statement: string;
  authority: Authority;
  confidence: number | null;
  sources: SourceEvidence[];
  evidence_count: number;
  extraction: {
    id: string;
    event_id: string;
    extractor_model: string;
    embedding_model: string;
    status: string;
    error: string | null;
    created_at: string;
  } | null;
  relationships: ClaimRelationship[];
  risk_flags: string[];
  risk_assessment: "not_recorded" | string;
};

export type ClaimsResponse = {
  items: OperatorClaim[];
  page: number;
  page_size: number;
  total: number;
  status_counts: Partial<Record<ClaimStatus, number>>;
};

export type ReviewQueueResponse = {
  items: OperatorClaim[];
  page: number;
  page_size: number;
  total: number;
  metrics: { candidate: number; conflicted: number; quarantined: number; failed_extraction: number };
};

export type ExplainResponse = {
  claim: Omit<OperatorClaim, "statement" | "authority" | "confidence" | "sources" | "evidence_count" | "extraction" | "relationships" | "risk_flags" | "risk_assessment">;
  evidence: Array<{ id: string; event: { id: string; source_kind: string; authority: Exclude<Authority, null>; credential_id: string | null; credential: { role: string; label: string; revoked_at: string | null } | null; actor_ref: string | null; payload: Record<string, unknown>; recorded_at: string } }>;
  relationships: ClaimRelationship[];
  conflict_reviews: Array<{ case_relationship_id: string; decision: string; superseding_claim_id: string | null; reason: string; reviewer_credential_id: string; created_at: string }>;
  actions: Array<{ action: string; old_status: string | null; new_status: string | null; reason: string; actor_ref: string; credential_id: string | null; created_at: string }>;
  extractions: Array<{ id: string; event_id: string; extractor_model: string; embedding_model: string; status: string; facts: Array<Record<string, unknown>>; error: string | null; created_at: string }>;
  retrievals: Array<{ id: string; created_at: string }>;
  action_influence: string;
};

export type ConflictCase = {
  id: string;
  from_claim_id: string;
  to_claim_id: string;
  from_claim: OperatorClaim;
  to_claim: OperatorClaim;
  reason: string;
  created_at: string;
};

export type ScopeItem = {
  id: string;
  project_id: string | null;
  project_name: string | null;
  parent_id: string | null;
  kind: "organization" | "project" | "branch";
  key: string;
  created_at: string;
  claim_counts: Partial<Record<ClaimStatus, number>>;
  claim_total: number;
  agents: Array<{ id: string; name: string; session_count: number; last_active: string }>;
};

export type ScopeResponse = { organization: { id: string; name: string }; items: ScopeItem[] };

export type OperatorContext = {
  organization: { id: string; name: string };
  principal: { id: string; role: string; label: string };
  selected_scope_id: string | null;
  projects: Array<{ id: string; name: string; created_at: string }>;
  scopes: Array<{ id: string; project_id: string | null; parent_id: string | null; kind: string; key: string; created_at: string }>;
};

export type RetrievalSummary = { id: string; scope_id: string; predicate: string | null; query_text: string | null; method: string; actor_ref: string; created_at: string; claim_count: number };

export type IntegrationsResponse = {
  credentials: Array<{ id: string; role: string; label: string; created_at: string; revoked_at: string | null }>;
  agents: Array<{ id: string; name: string; created_at: string; session_count: number; last_active: string | null }>;
  extractions: Array<{ id: string; extractor_model: string; embedding_model: string; status: string; error: string | null; created_at: string }>;
  raw_keys_exposed: false;
};

export type AuditItem = { id: string; claim_id: string; action: string; version: number | null; old_status: string | null; new_status: string | null; reason: string; actor_ref: string; credential_id: string | null; created_at: string };
