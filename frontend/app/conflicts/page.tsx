import { AppShell } from "@/components/shell";
import { ConflictDecisionForm } from "@/components/interactions";
import { Badge, Code, DataState, PageHeader, Panel, type Status } from "@/components/ui";
import { configuredScope, load, provena } from "@/lib/provena/server";
import type { OperatorClaim } from "@/lib/provena/types";
import { formatDate, payloadText } from "@/lib/provena/view-models";
import { AlertTriangle, Network } from "lucide-react";
import Link from "next/link";

export const metadata = { title: "Conflict Review" };
export const dynamic = "force-dynamic";

function ClaimSide({ claim, label, recent }: { claim: OperatorClaim; label: string; recent?: boolean }) {
  const source = claim.sources[0];
  return <Panel className="conflict-claim"><div className="conflict-title"><h2><i className={recent?"dot amber":"dot blue"}/>{label}</h2><Badge tone={claim.status as Status}>{claim.status}</Badge></div><div className="conflict-body">
    <span className="eyebrow">Proposition assertion</span><pre className="light-code">{JSON.stringify({ [`${claim.subject}.${claim.predicate}`]: claim.value }, null, 2)}</pre>
    <div className="human-extract"><span>Stored proposition</span><strong>{claim.subject}.{claim.predicate}</strong></div>
    <div className="kv-grid grid-2"><div className="kv"><label>Claim Identifier</label><code>{claim.id}</code></div><div className="kv"><label>Evidence authority</label><span>{claim.authority ?? "Unavailable"}</span></div><div className="kv"><label>Source ingestion type</label><Code>{source?.source_kind ?? "Unavailable"}</Code></div><div className="kv"><label>Recorded timestamp</label><code>{formatDate(claim.recorded_at)}</code></div></div>
    <div className="temporal"><span>Temporal horizon:</span><code>[{claim.valid_from ? formatDate(claim.valid_from) : "unspecified"} → {claim.valid_to ? formatDate(claim.valid_to) : "open-ended"}]</code></div>
    <div className="evidence-snippet"><span className="eyebrow">Evidence corpus snippet</span><em>{source ? payloadText(source.payload) : "Evidence projection unavailable"}</em></div>
    <div className={recent?"retrieval-warning":"retrieval-foot"}>{recent?<AlertTriangle size={13}/> : "◉"}<b>{claim.evidence_count} evidence links</b><code>claim: {claim.id.slice(0,8)}</code></div>
  </div></Panel>;
}

export default async function ConflictPage({ searchParams }: { searchParams: Promise<{ scope?: string; case?: string }> }) {
  const params = await searchParams;
  let scopeId: string;
  try { scopeId = configuredScope(params.scope); }
  catch (error) { return <AppShell active="/conflicts"><div className="content"><DataState title="Console scope is not configured" message={(error as Error).message} tone="danger"/></div></AppShell>; }
  const result = await load(() => provena.conflicts(scopeId));
  if (result.data === null) return <AppShell active="/conflicts" scopeId={scopeId}><div className="content"><DataState title="Conflicts could not be loaded" message={result.error} tone="danger"/></div></AppShell>;
  const cases = result.data.cases;
  const selected = cases.find(item => item.id === params.case) ?? cases[0];
  return <AppShell active="/conflicts" scopeId={scopeId}><div className="content conflict-page">
    <PageHeader title="Conflict Review" badge={<Badge tone="candidate">{cases.length} Unresolved Conflicts</Badge>} description="Reconcile recorded assertions without destroying either claim or its source evidence." />
    {!selected ? <DataState title="No unresolved conflicts" message="New overlapping claims with different values will appear here for review."/> : <>
      <div className="conflict-tabs">{cases.slice(0,3).map((item,index)=><Link aria-current={item.id === selected.id ? "page" : undefined} className={item.id === selected.id ? "active" : ""} href={`/conflicts?scope=${scopeId}&case=${item.id}`} key={item.id}><b>CONFLICT {index+1} OF {cases.length}</b><code>{item.from_claim.subject}.{item.from_claim.predicate}</code><span>{JSON.stringify(item.to_claim.value)} vs {JSON.stringify(item.from_claim.value)}</span></Link>)}</div>
      <div className="notice conflict-alert"><Network size={23}/><div><b>RECORDED POSSIBLE CONFLICT</b><p>{selected.reason}</p></div><Code>Case: {selected.id.slice(0,8)}</Code></div>
      <div className="grid-2 claim-compare"><ClaimSide claim={selected.to_claim} label="Claim A"/><ClaimSide claim={selected.from_claim} label="Claim B" recent/></div>
      <Panel className="chronology"><div className="chronology-head"><b>⌁ ASSERTION CHRONOLOGY &amp; FACT VALIDITY</b><code>Recording order does not determine truth</code></div><div className="timebar"><i/><span/><i/><span/><i/></div><div className="time-labels"><span>{formatDate(selected.to_claim.recorded_at)}<br/><b>Claim A recorded</b></span><span>Operator evidence review</span><span>{formatDate(selected.from_claim.recorded_at)}<br/><b>Claim B recorded</b></span></div></Panel>
      <Panel className="decision"><div className="decision-head"><h2>Reviewer Decision Matrix</h2><p>Each decision and reason is appended to the immutable conflict review history.</p></div><div className="decision-options"><ConflictDecisionForm caseId={selected.id} decision="temporal_change" supersedingClaimId={selected.from_claim.id} title="Claim B supersedes Claim A" description="Record a temporal change with Claim B as the newer proposition."/><ConflictDecisionForm caseId={selected.id} decision="temporal_change" supersedingClaimId={selected.to_claim.id} title="Claim A supersedes Claim B" description="Record a temporal change with Claim A as the controlling proposition."/><ConflictDecisionForm caseId={selected.id} decision="contradiction" title="Contradiction" description="Record that both propositions directly contradict each other."/><ConflictDecisionForm caseId={selected.id} decision="dismissed" title="Dismiss possible conflict" description="The propositions do not require a conflict relationship after review."/></div></Panel>
    </>}
  </div></AppShell>;
}
