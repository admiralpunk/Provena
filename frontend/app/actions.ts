"use server";

import { revalidatePath } from "next/cache";
import { provena } from "@/lib/provena/server";

type AssertionValues = {
  evidence: string;
  subject: string;
  predicate: string;
  value: string;
  validFrom: string;
  validTo: string;
};

export type ActionState = { ok: boolean; message: string; claimId?: string; values?: AssertionValues } | null;

function required(formData: FormData, key: string) {
  const value = formData.get(key);
  if (typeof value !== "string" || !value.trim()) throw new Error(`${key.replaceAll("_", " ")} is required`);
  return value.trim();
}

function resultError(error: unknown, values?: AssertionValues) {
  return { ok: false, message: error instanceof Error ? error.message : "The operation could not be completed.", values };
}

export async function assertClaim(_previous: ActionState, formData: FormData): Promise<ActionState> {
  const values = {
    evidence: String(formData.get("evidence") ?? ""),
    subject: String(formData.get("subject") ?? ""),
    predicate: String(formData.get("predicate") ?? ""),
    value: String(formData.get("value") ?? ""),
    validFrom: String(formData.get("valid_from") ?? ""),
    validTo: String(formData.get("valid_to") ?? ""),
  };
  try {
    const scopeId = required(formData, "scope_id");
    const evidence = required(formData, "evidence");
    const subject = required(formData, "subject");
    const predicate = required(formData, "predicate");
    const rawValue = required(formData, "value");
    const parsed: unknown = JSON.parse(rawValue);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) throw new Error("Value must be a JSON object.");
    const validFrom = String(formData.get("valid_from") ?? "").trim();
    const validTo = String(formData.get("valid_to") ?? "").trim();
    if (validFrom && validTo && validFrom >= validTo) throw new Error("Valid from must be before valid to.");
    const response = await provena.remember({
      scope_id: scopeId,
      source_kind: "user_statement",
      actor_ref: "operator-console:manual-assertion",
      text: evidence,
      proposition: {
        subject,
        predicate,
        value: parsed as Record<string, unknown>,
        ...(validFrom ? { valid_from: `${validFrom}T00:00:00Z` } : {}),
        ...(validTo ? { valid_to: `${validTo}T00:00:00Z` } : {}),
      },
    });
    revalidatePath("/overview");
    revalidatePath("/review");
    revalidatePath("/memories");
    return { ok: true, message: `Candidate claim created with evidence event ${response.event.id}.`, claimId: response.claim.id };
  } catch (error) {
    return resultError(error, values);
  }
}

export async function changeClaimStatus(_previous: ActionState, formData: FormData): Promise<ActionState> {
  try {
    const claimId = required(formData, "claim_id");
    const status = required(formData, "status");
    const reason = required(formData, "reason");
    await provena.updateStatus(claimId, status, reason);
    revalidatePath("/overview");
    revalidatePath("/review");
    revalidatePath("/memories");
    revalidatePath(`/memories/${claimId}`);
    return { ok: true, message: `Claim status changed to ${status}.`, claimId };
  } catch (error) {
    return resultError(error);
  }
}

export async function reviewConflict(_previous: ActionState, formData: FormData): Promise<ActionState> {
  try {
    const caseId = required(formData, "case_id");
    const decision = required(formData, "decision");
    const reason = required(formData, "reason");
    const superseding = formData.get("superseding_claim_id");
    await provena.reviewConflict(caseId, {
      decision,
      reason,
      ...(typeof superseding === "string" && superseding ? { superseding_claim_id: superseding } : {}),
    });
    revalidatePath("/overview");
    revalidatePath("/conflicts");
    revalidatePath("/memories");
    return { ok: true, message: "Conflict decision recorded." };
  } catch (error) {
    return resultError(error);
  }
}
