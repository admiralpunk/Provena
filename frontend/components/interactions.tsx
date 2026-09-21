"use client";

import Link from "next/link";
import { useActionState, useRef, useState } from "react";
import { assertClaim, changeClaimStatus, reviewConflict, type ActionState } from "@/app/actions";
import { Button } from "./ui";
import { Copy, Plus, X } from "lucide-react";

function ActionMessage({ state }: { state: ActionState }) {
  if (!state) return null;
  return <p className={state.ok ? "form-message form-success" : "form-message form-error"} role={state.ok ? "status" : "alert"}>{state.message}</p>;
}

export function CopyButton({ value, label = "Copy", compact = false }: { value: string; label?: string; compact?: boolean }) {
  const [status, setStatus] = useState<"idle" | "copied" | "error">("idle");
  function fallbackCopy() {
    const field = document.createElement("textarea");
    field.value = value;
    field.style.position = "fixed";
    field.style.opacity = "0";
    document.body.appendChild(field);
    field.select();
    const copied = document.execCommand("copy");
    field.remove();
    if (!copied) throw new Error("copy unavailable");
  }
  async function copy() {
    try {
      if (navigator.clipboard?.writeText) await navigator.clipboard.writeText(value);
      else fallbackCopy();
      setStatus("copied");
      window.setTimeout(() => setStatus("idle"), 1800);
    } catch {
      try { fallbackCopy(); setStatus("copied"); window.setTimeout(() => setStatus("idle"), 1800); }
      catch { setStatus("error"); }
    }
  }
  return <Button compact={compact} onClick={copy} aria-live="polite"><Copy size={12}/>{status === "copied" ? "Copied" : status === "error" ? "Copy failed" : label}</Button>;
}

export function AssertClaimDialog({ scopeId }: { scopeId: string }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [state, action, pending] = useActionState(assertClaim, null);
  return <>
    <Button variant="primary" onClick={() => dialog.current?.showModal()}><Plus size={14}/>Manually Assert Claim</Button>
    <dialog className="modal" ref={dialog} aria-labelledby="assert-claim-title">
      <div className="modal-head"><div><span className="eyebrow">EVIDENCE-BACKED WRITE</span><h2 id="assert-claim-title">Manually assert a claim</h2></div><button type="button" className="icon-button" aria-label="Close assertion form" onClick={() => dialog.current?.close()}><X size={18}/></button></div>
      {state?.ok ? <div className="modal-body stack"><ActionMessage state={state}/>{state.claimId && <Link className="button button-blue" href={`/memories/${state.claimId}`}>Explain created claim</Link>}<Button onClick={() => dialog.current?.close()}>Close</Button></div> : <form action={action} className="modal-body assertion-form">
        <input type="hidden" name="scope_id" value={scopeId}/>
        <p className="notice">The evidence event and candidate claim are created atomically. The source text is untrusted and does not authorize an action.</p>
        <label className="wide">Original evidence statement<textarea name="evidence" required minLength={3} maxLength={65536} defaultValue={state?.values?.evidence} placeholder="What was observed or stated?"/></label>
        <label>Subject<input name="subject" required maxLength={300} defaultValue={state?.values?.subject} placeholder="project"/></label>
        <label>Predicate<input name="predicate" required maxLength={200} defaultValue={state?.values?.predicate} placeholder="production_database"/></label>
        <label className="wide">Value (JSON object)<textarea name="value" required defaultValue={state?.values?.value ?? '{"name":"PostgreSQL"}'}/></label>
        <label>Valid from (optional)<input name="valid_from" type="date" defaultValue={state?.values?.validFrom}/></label>
        <label>Valid to (optional)<input name="valid_to" type="date" defaultValue={state?.values?.validTo}/></label>
        <ActionMessage state={state}/>
        <div className="modal-actions wide"><Button type="button" onClick={() => dialog.current?.close()}>Cancel</Button><Button type="submit" variant="primary" disabled={pending}>{pending ? "Creating…" : "Create candidate claim"}</Button></div>
      </form>}
    </dialog>
  </>;
}

export function ClaimStatusControl({ claimId, transitions, compact = false }: { claimId: string; transitions: Array<{ status: string; label: string }>; compact?: boolean }) {
  const [state, action, pending] = useActionState(changeClaimStatus, null);
  return <details className={compact ? "review-action-menu" : "claim-review-menu"}><summary>Change status</summary><form action={action}><input type="hidden" name="claim_id" value={claimId}/><label>Immutable reviewer reason<input name="reason" required minLength={3} maxLength={2000} placeholder="Why should this status change?"/></label><div className="cluster">{transitions.map(item=><button disabled={pending} key={item.status} name="status" value={item.status}>{pending ? "Saving…" : item.label}</button>)}</div><ActionMessage state={state}/></form></details>;
}

export function ConflictDecisionForm({ caseId, decision, title, description, supersedingClaimId }: { caseId: string; decision: string; title: string; description: string; supersedingClaimId?: string }) {
  const [state, action, pending] = useActionState(reviewConflict, null);
  return <form action={action} className="conflict-decision-form"><input type="hidden" name="case_id" value={caseId}/><input type="hidden" name="decision" value={decision}/>{supersedingClaimId && <input type="hidden" name="superseding_claim_id" value={supersedingClaimId}/>}<b>{title}</b><span>{description}</span><label>Immutable reviewer reason<textarea name="reason" required minLength={3} maxLength={2000} placeholder="Explain the evidence and decision."/></label><Button variant={decision === "temporal_change" ? "blue" : "secondary"} type="submit" disabled={pending}>{pending ? "Recording…" : "Record decision"}</Button><ActionMessage state={state}/></form>;
}
