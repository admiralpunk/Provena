import Link from "next/link";
import { AppShell } from "@/components/shell";
import { Badge, Code, DataState, MetricCard, PageHeader, Panel, PanelHeader } from "@/components/ui";
import { configuredScope, load, provena } from "@/lib/provena/server";
import { formatDate } from "@/lib/provena/view-models";

export const metadata = { title: "Overview" };
export const dynamic = "force-dynamic";

export default async function OverviewPage({ searchParams }: { searchParams: Promise<{ scope?: string }> }) {
  const params = await searchParams;
  let scopeId: string;
  try { scopeId = configuredScope(params.scope); }
  catch (error) { return <AppShell active="/overview"><div className="content"><DataState title="Console scope is not configured" message={(error as Error).message} tone="danger"/></div></AppShell>; }
  const result = await load(async () => {
    const [overview, claims, retrievals] = await Promise.all([
      provena.overview(scopeId),
      provena.claims(scopeId, { pageSize: 6 }),
      provena.retrievals(scopeId),
    ]);
    return { overview, claims, retrievals };
  });
  if (result.data === null) return <AppShell active="/overview" scopeId={scopeId}><div className="content"><DataState title="Overview could not be loaded" message={result.error} tone="danger"/></div></AppShell>;
  const { overview, claims, retrievals } = result.data;
  const total = Object.values(overview.status_counts).reduce((sum, count) => sum + count, 0);
  return <AppShell active="/overview" scopeId={scopeId}><div className="content overview-page">
    <PageHeader title="Memory Operations Overview" description="Current exact-scope totals derived from PostgreSQL records." badge={<Code>scope: {scopeId.slice(0,8)}…</Code>}/>
    <div className="metrics"><MetricCard label="Claims" value={total}/><MetricCard label="Candidates" value={overview.status_counts.candidate ?? 0} tone="amber"/><MetricCard label="Retrievals" value={overview.retrieval_count} tone="active"/><MetricCard label="Failed extractions" value={overview.failed_extraction_count} tone={overview.failed_extraction_count ? "conflicted" : "neutral"}/></div>
    <Panel className="overview-retrievals"><PanelHeader title="Recent agent retrievals" actions={<Link href={`/retrievals?scope=${scopeId}`}>View retrieval history →</Link>}/>
      {retrievals.items.length ? <div className="table-wrap"><table className="data-table overview-table"><colgroup><col className="overview-date-col"/><col/><col className="overview-method-col"/><col className="overview-count-col"/><col className="overview-action-col"/></colgroup><thead><tr><th>Date</th><th>Query or predicate</th><th>Method</th><th className="numeric-cell">No. of Claims</th><th><span className="sr-only">Open retrieval</span></th></tr></thead><tbody>{retrievals.items.slice(0,8).map(item=><tr key={item.id}><td data-label="Date"><time dateTime={item.created_at}>{formatDate(item.created_at)}</time></td><td data-label="Query"><span className="overview-query">{item.query_text ?? item.predicate ?? "Exact-scope retrieval"}</span></td><td data-label="Method"><Badge>{item.method}</Badge></td><td data-label="No. of Claims" className="numeric-cell"><strong>{item.claim_count}</strong></td><td className="row-action"><Link aria-label={`Inspect retrieval from ${formatDate(item.created_at)}`} href={`/retrievals?scope=${scopeId}&retrieval=${item.id}`}>Inspect →</Link></td></tr>)}</tbody></table></div> : <DataState title="No retrievals recorded" message="Agent retrievals for this scope will appear here."/>}
    </Panel>
    <Panel><PanelHeader title="Recent ledger claims" actions={<Link href={`/memories?scope=${scopeId}`}>View all claims →</Link>}/>{claims.items.length ? <div className="relationship-list">{claims.items.map(claim=><div key={claim.id}><Badge tone={claim.status}>{claim.status}</Badge><span><Link className="link-token" href={`/memories/${claim.id}`}>{claim.subject}.{claim.predicate}</Link></span><Code>{formatDate(claim.recorded_at)}</Code></div>)}</div> : <DataState title="No claims in this scope" message="Create an evidence-backed candidate claim from Memory Explorer."/>}</Panel>
  </div></AppShell>;
}
