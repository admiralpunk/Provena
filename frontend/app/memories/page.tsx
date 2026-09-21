import Link from "next/link";
import { AppShell } from "@/components/shell";
import { ClaimTable } from "@/components/claim-table";
import { AssertClaimDialog } from "@/components/interactions";
import { Button, Code, DataState, MetricCard, PageHeader } from "@/components/ui";
import { configuredScope, load, provena } from "@/lib/provena/server";
import { claimRow } from "@/lib/provena/view-models";
import { Search } from "lucide-react";

export const metadata = { title: "Memory Explorer" };
export const dynamic = "force-dynamic";

type SearchParams = Promise<{ scope?: string; q?: string; status?: string; page?: string }>;

export default async function MemoriesPage({ searchParams }: { searchParams: SearchParams }) {
  const params = await searchParams;
  let scopeId: string;
  try {
    scopeId = configuredScope(params.scope);
  } catch (error) {
    return <AppShell active="/memories"><div className="content"><DataState title="Console scope is not configured" message={(error as Error).message} tone="danger" /></div></AppShell>;
  }
  const page = Math.max(1, Number(params.page) || 1);
  const result = await load(() => provena.claims(scopeId, { page, pageSize: 25, q: params.q, status: params.status }));
  if (result.data === null) return <AppShell active="/memories" scopeId={scopeId}><div className="content"><DataState title="Claims could not be loaded" message={result.error} tone="danger" /></div></AppShell>;

  const data = result.data;
  const rows = data.items.map(claimRow);
  const pages = Math.max(1, Math.ceil(data.total / data.page_size));
  const href = (nextPage: number) => `/memories?${new URLSearchParams({ scope: scopeId, ...(params.q ? { q: params.q } : {}), ...(params.status ? { status: params.status } : {}), page: String(nextPage) })}`;
  return <AppShell active="/memories" scopeId={scopeId}><div className="content">
    <PageHeader title="Memory Explorer" description="Searchable registry of versioned claims, propositions, and historical assertions across partitioned agent scopes." badge={<span className="version">immutable ledger</span>} actions={<AssertClaimDialog scopeId={scopeId}/>} />
    <div className="metrics metrics-6">
      <MetricCard label="Total claims" value={Object.values(data.status_counts).reduce((sum, count) => sum + (count ?? 0), 0)}/>
      <MetricCard label="Verified" value={data.status_counts.verified ?? 0} tone="verified"/>
      <MetricCard label="Active" value={data.status_counts.active ?? 0} tone="active"/>
      <MetricCard label="Candidate" value={data.status_counts.candidate ?? 0} tone="amber"/>
      <MetricCard label="Conflicted" value={data.status_counts.conflicted ?? 0} tone="conflicted"/>
      <MetricCard label="Quarantined" value={data.status_counts.quarantined ?? 0}/>
    </div>
    <section className="filter-panel">
      <form className="filter-search" method="get"><b>FILTER &gt;</b><input type="hidden" name="scope" value={scopeId}/><input name="q" defaultValue={params.q} aria-label="Filter claims" placeholder="Filter by subject, predicate, or proposition value..."/><Search size={16}/><Button compact type="submit">Apply</Button><Link className="button button-secondary button-compact" href={`/memories?scope=${scopeId}`}>Clear Filters</Link></form>
      <div className="filter-row"><Code>Scope: {scopeId.slice(0, 8)}…</Code><Link className={!params.status ? "filter-chip active" : "filter-chip"} href={`/memories?scope=${scopeId}`}>all</Link>{["candidate","active","verified","conflicted","superseded","quarantined","expired","ephemeral","deleted"].map(status=><Link aria-current={params.status === status ? "page" : undefined} className={params.status === status ? "filter-chip active" : "filter-chip"} href={`/memories?scope=${scopeId}&status=${status}`} key={status}>{status}</Link>)}</div>
    </section>
    <section className="panel memory-ledger">
      <div className="ledger-toolbar"><span>{data.total} MATCHING</span><b>SORT: Recorded Time (DESC) ↓</b></div>
      {rows.length ? <ClaimTable rows={rows}/> : <DataState title="No claims match this view" message="Change the status or text filter to inspect other ledger records."/>}
      <footer className="pagination"><span>Showing <b>{rows.length ? (page - 1) * data.page_size + 1 : 0}-{Math.min(page * data.page_size, data.total)}</b> of <b>{data.total}</b> claims</span><span>Page {page} of {pages}</span><nav className="cluster" aria-label="Claim pages">{page === 1 ? <span aria-disabled="true">‹</span> : <Link aria-label="Previous page" href={href(page - 1)}>‹</Link>}<span className="current">{page}</span>{page === pages ? <span aria-disabled="true">›</span> : <Link aria-label="Next page" href={href(page + 1)}>›</Link>}</nav></footer>
    </section>
  </div></AppShell>;
}
