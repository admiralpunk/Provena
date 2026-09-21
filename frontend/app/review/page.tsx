import Link from "next/link";
import { AppShell } from "@/components/shell";
import { ClaimStatusControl } from "@/components/interactions";
import { Badge, Code, DataState, MetricCard, PageHeader, Progress } from "@/components/ui";
import { configuredScope, load, provena } from "@/lib/provena/server";
import { formatDate, payloadText } from "@/lib/provena/view-models";
import { AlertTriangle, Filter, ShieldAlert } from "lucide-react";

export const metadata = { title: "Review Inbox" };
export const dynamic = "force-dynamic";

export default async function ReviewPage({ searchParams }: { searchParams: Promise<{ scope?: string }> }) {
  const params = await searchParams;
  let scopeId: string;
  try { scopeId = configuredScope(params.scope); }
  catch (error) { return <AppShell active="/review"><div className="content"><DataState title="Console scope is not configured" message={(error as Error).message} tone="danger"/></div></AppShell>; }
  const result = await load(() => provena.reviewQueue(scopeId));
  if (result.data === null) return <AppShell active="/review" scopeId={scopeId}><div className="content"><DataState title="Review queue could not be loaded" message={result.error} tone="danger"/></div></AppShell>;
  const { items, metrics } = result.data;
  return <AppShell active="/review" scopeId={scopeId}><div className="content">
    <PageHeader title="Review Inbox" badge={<Code>pipeline: candidate-triage</Code>} description="Review candidate memories against their original evidence before changing retrieval state." />
    <div className="metrics">
      <MetricCard label="Candidate queue" value={metrics.candidate} tone="amber" detail="Awaiting operator review" />
      <MetricCard label="Possible conflicts" value={metrics.conflicted} tone="conflicted" detail="Unresolved related claims" />
      <MetricCard label="Quarantined" value={metrics.quarantined} tone="quarantined" detail="Excluded pending review" />
      <MetricCard label="Failed extraction" value={metrics.failed_extraction} detail="Recorded extraction failures" />
    </div>
    <section className="filter-panel"><div className="filter-search"><Filter size={15}/><b>QUEUE &gt;</b><span className="muted">Candidate claims grouped by immutable source evidence</span></div><div className="filter-row"><Code>Scope: {scopeId.slice(0,8)}…</Code><Badge tone="candidate">Status: Candidate</Badge><Badge>Authority: All recorded</Badge><span className="filter-danger">Risk flags: recorded only</span></div></section>
    {!items.length && <DataState title="The review queue is empty" message="New candidate claims for this exact scope will appear here."/>}
    {items.map((claim) => {
      const source = claim.sources[0];
      const confidence = claim.confidence === null ? null : Math.round(claim.confidence * 100);
      return <section className="review-group clean-group" key={claim.id}>
        <div className="review-group-head"><span className="cluster"><Badge>{source?.source_kind ?? "source unavailable"}</Badge><Badge tone={claim.authority === "high" ? "high" : claim.authority === "low" ? "low" : "neutral"}>Authority: {claim.authority ?? "unavailable"}</Badge><Code>{source?.event_id ?? "no event"}</Code><span>· {formatDate(claim.recorded_at)}</span></span><Link className="button button-secondary button-compact" href={`/memories/${claim.id}`}>Explain Claim</Link></div>
        <div className="source-line"><span>♧</span><b>Source Event:</b><em>{source ? payloadText(source.payload) : "Evidence projection unavailable"}</em></div>
        {claim.risk_assessment === "not_recorded" && <div className="notice notice-warn"><AlertTriangle size={17}/><span><b>Risk assessment unavailable:</b> no audited security-policy decision is recorded for this claim. The console does not infer one.</span></div>}
        <div className="review-columns"><span>Proposition &amp; triple assertion</span><span>Status / authority</span><span>Confidence</span><span>Risk flags</span><span>Actions</span></div>
        <div className="review-row"><div><div className="review-proposition"><b className="link-token mono">{claim.subject}</b><span>.</span><b className="mono">{claim.predicate}</b><span>=</span><Code>{JSON.stringify(claim.value)}</Code></div><div className="review-meta">Scope: <b>{claim.scope_id.slice(0,8)}…</b> • Evidence: <b>{claim.evidence_count}</b> • Claim: <b>{claim.id.slice(0,8)}…</b></div></div><div><Badge tone="candidate">Candidate</Badge><div className="mono-small">Auth: {claim.authority?.toUpperCase() ?? "N/A"}</div></div><div>{confidence === null ? <span className="mono-small">Not recorded</span> : <><Progress value={confidence} tone={claim.authority === "high" ? "green" : "blue"}/><span className="mono-small">{confidence}%</span></>}</div><div>{claim.risk_flags.length ? claim.risk_flags.map(flag=><Badge key={flag} tone="candidate">{flag}</Badge>) : <Badge>Not recorded</Badge>}</div><ClaimStatusControl compact claimId={claim.id} transitions={[{status:"active",label:"Activate"},{status:"quarantined",label:"Quarantine"},{status:"deleted",label:"Reject"}]}/></div>
      </section>;
    })}
    <div className="notice retention"><ShieldAlert size={17}/><span><b>Retention Policy Notice:</b> Rejecting a claim changes its state to deleted while its original event, evidence link, and operator action remain in the append-only ledger.</span><Link href={`/settings?scope=${scopeId}`}>View Retention Rules →</Link></div>
  </div></AppShell>;
}
