import Link from "next/link";
import { AppShell } from "@/components/shell";
import { Badge, Code, DataState, PageHeader, Panel, PanelHeader } from "@/components/ui";
import { configuredScope, load, provena } from "@/lib/provena/server";
import { formatDate } from "@/lib/provena/view-models";

export const metadata = { title: "Audit log" };
export const dynamic = "force-dynamic";

export default async function AuditPage({ searchParams }: { searchParams: Promise<{ scope?: string }> }) {
  const params = await searchParams;
  let scopeId: string;
  try { scopeId = configuredScope(params.scope); }
  catch (error) { return <AppShell active="/audit"><div className="content"><DataState title="Console scope is not configured" message={(error as Error).message} tone="danger"/></div></AppShell>; }
  const result = await load(() => provena.audit(scopeId));
  if (result.data === null) return <AppShell active="/audit" scopeId={scopeId}><div className="content"><DataState title="Audit log could not be loaded" message={result.error} tone="danger"/></div></AppShell>;
  return <AppShell active="/audit" scopeId={scopeId}><div className="content">
    <PageHeader eyebrow={<><Code>APPEND-ONLY LEDGER</Code><Badge tone="verified">Organization filtered</Badge></>} title="Audit Log" description="Recorded memory actions for the selected exact scope. Browsing this page does not append a retrieval event." badge={<Code>scope: {scopeId}</Code>}/>
    <Panel><PanelHeader title={`${result.data.items.length} MOST RECENT ACTIONS`} actions={<Code>LIMIT 100</Code>}/>
      {result.data.items.length ? <div className="table-wrap"><table className="data-table"><thead><tr><th>Recorded</th><th>Action</th><th>Claim</th><th>State transition</th><th>Actor</th><th>Reason</th></tr></thead><tbody>{result.data.items.map(item=><tr key={item.id}><td>{formatDate(item.created_at)}</td><td><Badge>{item.action}</Badge></td><td><Link className="link-token mono" href={`/memories/${item.claim_id}`}>{item.claim_id.slice(0,8)}…</Link></td><td><Code>{item.old_status ?? "∅"} → {item.new_status ?? "∅"}</Code>{item.version !== null && <small> v{item.version}</small>}</td><td><span className="mono-small">{item.actor_ref}</span></td><td>{item.reason}</td></tr>)}</tbody></table></div> : <DataState title="No audit actions in this scope" message="Actions appear here when claims are created, extracted, reviewed, or related."/>}
    </Panel>
  </div></AppShell>;
}
