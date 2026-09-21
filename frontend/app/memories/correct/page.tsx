import Link from "next/link";
import { AppShell } from "@/components/shell";
import { Badge, Code, DataState, PageHeader, Panel, PanelHeader } from "@/components/ui";
import { load, provena } from "@/lib/provena/server";
import { formatDate, payloadText } from "@/lib/provena/view-models";
import { LockKeyhole, ShieldCheck } from "lucide-react";

export const metadata = { title: "Correct claim" };
export const dynamic = "force-dynamic";

export default async function CorrectionPage({ searchParams }: { searchParams: Promise<{ claim?: string }> }) {
  const { claim: claimId } = await searchParams;
  if (!claimId) return <AppShell active="/memories"><div className="content"><DataState title="Choose a claim to correct" message="Open a claim explanation and select Supersede."/></div></AppShell>;
  const result = await load(() => provena.explain(claimId));
  if (result.data === null) return <AppShell active="/memories"><div className="content"><DataState title="Claim could not be loaded" message={result.error} tone="danger"/></div></AppShell>;
  const { claim, evidence, actions, relationships } = result.data;
  const canSupersede = ["active", "verified", "conflicted"].includes(claim.status);
  return <AppShell active="/memories" scopeId={claim.scope_id}><div className="content correction-page">
    <PageHeader eyebrow={<><Code>NON-DESTRUCTIVE CORRECTION</Code><Badge tone={claim.status}>{claim.status}</Badge></>} title="Claim Supersession" description="Inspect the original proposition and evidence before creating a replacement claim." actions={<Link className="button button-secondary" href={`/memories/${claim.id}`}>Back to explanation</Link>}/>
    <div className="ledger-banner"><ShieldCheck size={30}/><div><b>DATABASE ENFORCED <Code>APPEND-ONLY HISTORY</Code></b><strong>The original proposition, validity interval, and evidence cannot be edited in place.</strong><span>A correction must create a new evidence-backed claim and an explicit supersedes relationship.</span></div></div>
    <div className="correction-summary">
      <Panel><PanelHeader title="ORIGINAL CLAIM" actions={<Code>{claim.id}</Code>}/><div className="panel-body stack"><div className="triple"><Code>sub: {claim.subject}</Code><span>→</span><Code>pred: {claim.predicate}</Code><span>→</span><Code>object: JSON</Code></div><pre className="code-block">{JSON.stringify(claim.value, null, 2)}</pre><div className="grid-2"><div className="kv"><label>Recorded</label><code>{formatDate(claim.recorded_at)}</code></div><div className="kv"><label>Validity</label><code>{claim.valid_from ? formatDate(claim.valid_from) : "unspecified"} → {claim.valid_to ? formatDate(claim.valid_to) : "open-ended"}</code></div><div className="kv"><label>Audit actions</label><strong>{actions.length}</strong></div><div className="kv"><label>Relationships</label><strong>{relationships.length}</strong></div></div></div></Panel>
      <Panel><PanelHeader title="SOURCE EVIDENCE" actions={<Badge>{evidence.length} links</Badge>}/><div className="panel-body stack">{evidence.map(item=><div className="source-card" key={item.id}><div><b>{item.event.source_kind}</b><Badge tone={item.event.authority === "high" ? "high" : item.event.authority === "low" ? "low" : "neutral"}>{item.event.authority}</Badge></div><blockquote>{payloadText(item.event.payload)}</blockquote><code>{item.event.id} · {formatDate(item.event.recorded_at)}</code></div>)}</div></Panel>
    </div>
    <Panel className="supersede"><PanelHeader title="ATOMIC SUPERSESSION COMMAND" actions={<Badge tone={canSupersede ? "candidate" : "conflicted"}>{canSupersede ? "Backend prerequisite pending" : `Cannot supersede ${claim.status}`}</Badge>}/><div className="panel-body stack"><div className="notice"><LockKeyhole size={18}/><span>The current database invariant makes claim validity immutable. FE-24 asks to update the old claim validity in the same command, so this mutation is not exposed until an ADR decides how temporal closure is represented.</span></div><div className="form-grid"><label>NEW SUBJECT<input value={claim.subject} readOnly/></label><label>NEW PREDICATE<input value={claim.predicate} readOnly/></label><label className="wide">NEW VALUE<textarea className="json-field" value={JSON.stringify(claim.value, null, 2)} readOnly/></label></div></div></Panel>
  </div></AppShell>;
}
