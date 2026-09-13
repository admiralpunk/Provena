import "server-only";

import type {
  AuditItem,
  ClaimsResponse,
  ConflictCase,
  ExplainResponse,
  IntegrationsResponse,
  OperatorClaim,
  OperatorContext,
  RetrievalSummary,
  ReviewQueueResponse,
  ScopeResponse,
} from "./types";

export class ProvenaAPIError extends Error {
  constructor(message: string, readonly status?: number) {
    super(message);
    this.name = "ProvenaAPIError";
  }
}

function configuration() {
  const apiUrl = process.env.PROVENA_API_URL?.replace(/\/$/, "");
  const apiKey = process.env.PROVENA_API_KEY;
  if (!apiUrl || !apiKey) {
    throw new ProvenaAPIError("Set PROVENA_API_URL and PROVENA_API_KEY on the Next.js server.");
  }
  return { apiUrl, apiKey };
}

export function configuredScope(requested?: string) {
  const scopeId = requested || process.env.PROVENA_SCOPE_ID;
  if (!scopeId) throw new ProvenaAPIError("Set PROVENA_SCOPE_ID or select a scope in the URL.");
  return scopeId;
}

function objectWith<T>(value: unknown, fields: string[], label: string): T {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new ProvenaAPIError(`Invalid ${label} response.`);
  const record = value as Record<string, unknown>;
  if (fields.some((field) => !(field in record))) throw new ProvenaAPIError(`Incomplete ${label} response.`);
  return value as T;
}

function collection<T>(value: unknown, label: string): T {
  const result = objectWith<T>(value, ["items"], label) as T & { items: unknown };
  if (!Array.isArray(result.items)) throw new ProvenaAPIError(`Invalid ${label} items.`);
  return result;
}

async function request<T>(path: string, init: RequestInit = {}, validate?: (value: unknown) => T): Promise<T> {
  const { apiUrl, apiKey } = configuration();
  const response = await fetch(`${apiUrl}${path}`, {
    ...init,
    cache: "no-store",
    signal: AbortSignal.timeout(8_000),
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      "X-API-Key": apiKey,
      ...init.headers,
    },
  });
  if (!response.ok) {
    let detail = `Provena API returned ${response.status}`;
    try {
      const payload = await response.json() as { detail?: string };
      if (payload.detail) detail = payload.detail;
    } catch {}
    throw new ProvenaAPIError(detail, response.status);
  }
  const payload: unknown = await response.json();
  return validate ? validate(payload) : objectWith<T>(payload, [], "API");
}

function query(values: Record<string, string | number | undefined>) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(values)) if (value !== undefined && value !== "") params.set(key, String(value));
  return params.toString();
}

export const provena = {
  context: (scopeId?: string) => request<OperatorContext>(`/operator/context?${query({ scope_id: scopeId })}`, {}, value => objectWith(value, ["organization", "principal", "projects", "scopes"], "operator context")),
  claims: (scopeId: string, options: { page?: number; pageSize?: number; status?: string; q?: string } = {}) => request<ClaimsResponse>(`/operator/claims?${query({ scope_id: scopeId, page: options.page, page_size: options.pageSize, status: options.status, q: options.q })}`, {}, value => collection(objectWith(value, ["page", "page_size", "total", "status_counts"], "claims"), "claims")),
  reviewQueue: (scopeId: string) => request<ReviewQueueResponse>(`/operator/review-queue?${query({ scope_id: scopeId })}`, {}, value => collection(objectWith(value, ["metrics", "total"], "review queue"), "review queue")),
  explain: (claimId: string) => request<ExplainResponse>(`/claims/${encodeURIComponent(claimId)}/explain`, {}, value => objectWith(value, ["claim", "evidence", "relationships", "actions", "extractions", "retrievals"], "claim explanation")),
  conflicts: (scopeId: string) => request<{ cases: ConflictCase[] }>(`/conflicts?${query({ scope_id: scopeId })}`, {}, value => objectWith(value, ["cases"], "conflicts")),
  scopes: () => request<ScopeResponse>("/operator/scopes", {}, value => objectWith(value, ["organization", "items"], "scopes")),
  retrievals: (scopeId: string) => request<{ items: RetrievalSummary[] }>(`/operator/retrievals?${query({ scope_id: scopeId })}`, {}, value => collection(value, "retrievals")),
  retrieval: (retrievalId: string) => request<{ retrieval: RetrievalSummary; claims: OperatorClaim[]; similarity_scores: string; filtering_diagnostics: string }>(`/operator/retrievals/${encodeURIComponent(retrievalId)}`, {}, value => objectWith(value, ["retrieval", "claims", "similarity_scores", "filtering_diagnostics"], "retrieval detail")),
  integrations: () => request<IntegrationsResponse>("/operator/integrations", {}, value => objectWith(value, ["credentials", "agents", "extractions", "raw_keys_exposed"], "integrations")),
  audit: (scopeId: string) => request<{ items: AuditItem[] }>(`/operator/audit?${query({ scope_id: scopeId })}`, {}, value => collection(value, "audit")),
  overview: (scopeId: string) => request<{ status_counts: Record<string, number>; retrieval_count: number; event_count: number; failed_extraction_count: number }>(`/operator/overview?${query({ scope_id: scopeId })}`, {}, value => objectWith(value, ["status_counts", "retrieval_count", "event_count", "failed_extraction_count"], "overview")),
  remember: (body: { scope_id: string; source_kind: "user_statement"; actor_ref: string; text: string; proposition: { subject: string; predicate: string; value: Record<string, unknown>; valid_from?: string; valid_to?: string } }) => request<{ event: { id: string }; claim: { id: string; status: string } }>("/memories", { method: "POST", body: JSON.stringify(body) }, value => objectWith(value, ["event", "claim"], "memory assertion")),
  updateStatus: (claimId: string, status: string, reason: string) => request(`/claims/${encodeURIComponent(claimId)}/status`, { method: "POST", body: JSON.stringify({ status, reason }) }),
  reviewConflict: (caseId: string, body: { decision: string; reason: string; superseding_claim_id?: string }) => request(`/conflicts/${encodeURIComponent(caseId)}/review`, { method: "POST", body: JSON.stringify(body) }),
};

export async function load<T>(loader: () => Promise<T>): Promise<{ data: T; error: null } | { data: null; error: string }> {
  try {
    return { data: await loader(), error: null };
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unable to load Provena data.";
    return { data: null, error: message };
  }
}
