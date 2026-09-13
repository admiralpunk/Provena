import type { OperatorClaim } from "./types";

export type ClaimRow = {
  id: string;
  title: string;
  subject: string;
  predicate: string;
  value: string;
  status: OperatorClaim["status"];
  authority: "Low" | "Medium" | "High" | "Ephemeral" | "Unavailable";
  confidence: number | null;
  relevance?: number | null;
  note?: string;
};

export function claimRow(claim: OperatorClaim): ClaimRow {
  const conflict = claim.relationships.find((relationship) => relationship.kind === "related_to" || relationship.kind === "contradicts");
  return {
    id: claim.id,
    title: `${claim.subject}.${claim.predicate}`,
    subject: claim.subject,
    predicate: claim.predicate,
    value: JSON.stringify(claim.value),
    status: claim.status,
    authority: claim.authority ? `${claim.authority[0].toUpperCase()}${claim.authority.slice(1)}` as ClaimRow["authority"] : "Unavailable",
    confidence: claim.confidence === null ? null : Math.round(claim.confidence * 100),
    relevance: null,
    note: conflict ? "Conflict recorded" : undefined,
  };
}

export function payloadText(payload: Record<string, unknown>) {
  const value = payload.text;
  return typeof value === "string" ? value : JSON.stringify(payload);
}

export function formatDate(value: string | null | undefined) {
  if (!value) return "Unavailable";
  return new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "medium", timeZone: "UTC" }).format(new Date(value));
}
