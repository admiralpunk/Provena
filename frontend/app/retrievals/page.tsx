import Link from "next/link";
import { AppShell } from "@/components/shell";
import { CopyButton } from "@/components/interactions";
import { Badge, Code, DataState, PageHeader, Panel } from "@/components/ui";
import { configuredScope, load, provena } from "@/lib/provena/server";
import { formatDate } from "@/lib/provena/view-models";
import { CheckCircle2, Filter, TerminalSquare } from "lucide-react";

export const metadata = { title: "Retrieval Explorer" };
export const dynamic = "force-dynamic";

export default async function RetrievalPage({ searchParams }: { searchParams: Promise<{ scope?: string; retrieval?: string }> }) {
  const params = await searchParams;
  let scopeId: string;
  try { scopeId = configuredScope(params.scope); }
  catch (error) { return <AppShell active="/retrievals"><div className="content"><DataState title="Console scope is not configured" message={(error as Error).message} tone="danger"/></div></AppShell>; }
  const history = await load(() => provena.retrievals(scopeId));
  if (history.data === null) return <AppShell active="/retrievals" scopeId={scopeId}><div className="content"><DataState title="Retrieval history could not be loaded" message={history.error} tone="danger"/></div></AppShell>;
  const selectedId = params.retrieval ?? history.data.items[0]?.id;
  const detail = selectedId ? await load(() => provena.retrieval(selectedId)) : null;
  return <AppShell active="/retrievals" scopeId={scopeId}><div className="content retrieval-page"><PageHeader eyebrow={<span>RETRIEVAL AUDIT // POSTGRESQL SYSTEM OF RECORD</span>} title="Retrieval Explorer" description="Inspect recorded agent retrievals and the exact claims delivered for context." actions={selectedId ? <CopyButton label="Copy retrieval ID" value={selectedId}/> : undefined}/>
    <Panel className="simulator"><div className="sim-head"><b><TerminalSquare size={15}/>RECORDED RETRIEVALS</b><code>{history.data.items.length} loaded</code></div><div className="panel-body"><div className="retrieval-picker">{history.data.items.map(item=><Link className={item.id===selectedId?"active":""} href={`/retrievals?scope=${scopeId}&retrieval=${item.id}`} key={item.id}><Code>{item.method}</Code><b>{item.query_text ?? item.predicate ?? "Exact-scope retrieval"}</b><span>{item.claim_count} claims · {formatDate(item.created_at)}</span></Link>)}</div></div></Panel>
    {!selectedId && <DataState title="No retrievals have been recorded" message="An agent retrieval through GET /claims will appear here; operator browsing does not create retrieval records."/>}
    {detail?.data && <><div className="sim-grid"><div><span>SCOPE BOUNDARY</span><b>{detail.data.retrieval.scope_id}</b><small>Exact tenant and scope filter</small></div><div><span>REQUESTING PRINCIPAL</span><b>{detail.data.retrieval.actor_ref}</b><small>Recorded actor reference</small></div><div><span>RESULT COUNT</span><b>{detail.data.claims.length} claims</b><small>Persisted RetrievalItem links</small></div><div><span>METHOD</span><b>{detail.data.retrieval.method}</b><small>{formatDate(detail.data.retrieval.created_at)}</small></div></div>
      <div className="retrieval-columns"><section><h2 className="section-heading"><span>⇥</span>Delivered Memories <Badge tone="active">{detail.data.claims.length} Claims</Badge></h2>{detail.data.claims.map(claim=><article className="injected-claim" key={claim.id}><div className="injected-head"><div><Badge tone={claim.status}>{claim.status}</Badge><Code>claim: {claim.id}</Code></div><strong>Rank unavailable<small>similarity not persisted</small></strong></div><h2>{claim.subject}.{claim.predicate}</h2><div className="predicate"><span className="eyebrow">Predicate assertion / JSON payload</span><code><b>{claim.subject}.{claim.predicate}</b> = {JSON.stringify(claim.value)}</code></div><div className="claim-stats"><div><span>EXTRACTION CONF.</span><b>{claim.confidence === null ? "Not recorded" : `${Math.round(claim.confidence*100)}%`}</b></div><div><span>SOURCE AUTHORITY</span><b>{claim.authority ?? "Unavailable"}</b></div><div><span>VALIDITY</span><b>{claim.valid_to ? `until ${formatDate(claim.valid_to)}` : "open-ended"}</b></div></div><footer><CheckCircle2 size={14}/>Persisted as a RetrievalItem for this event<Link href={`/memories/${claim.id}`}>Explain →</Link></footer></article>)}</section><aside><h2 className="section-heading"><Filter size={20}/>Filtering Diagnostics</h2><Panel className="excluded"><div><b>Similarity scores</b><Badge>Not recorded</Badge></div><p>The current retrieval ledger records membership but not rank or similarity. The console does not reconstruct missing scores.</p></Panel><Panel className="excluded"><div><b>Excluded candidates</b><Badge>Not recorded</Badge></div><p>Policy gate diagnostics are not persisted for this retrieval.</p></Panel></aside></div>
      <div className="prompt-payload"><header><b>RECORDED CONTEXT MEMBERSHIP</b><span><Code>retrieval: {detail.data.retrieval.id}</Code></span></header><pre>{detail.data.claims.map(claim=>`[${claim.status}] ${claim.subject}.${claim.predicate} = ${JSON.stringify(claim.value)}`).join("\n") || "No claims were delivered."}</pre><footer>Content is untrusted memory data.<span>Influence attribution: <b>not tracked</b></span></footer></div></>}
    {detail?.data === null && <DataState title="Retrieval detail could not be loaded" message={detail.error} tone="danger"/>}
  </div></AppShell>;
}
