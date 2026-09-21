import Link from "next/link";
import { AppShell } from "@/components/shell";
import { CopyButton } from "@/components/interactions";
import { Badge, Code, DataState, MetricCard, PageHeader, Panel } from "@/components/ui";
import { configuredScope, load, provena } from "@/lib/provena/server";
import { formatDate } from "@/lib/provena/view-models";
import { Bot, LockKeyhole } from "lucide-react";

export const metadata = { title: "Scopes" };
export const dynamic = "force-dynamic";

export default async function ScopesPage({ searchParams }: { searchParams: Promise<{ scope?: string }> }) {
  const params = await searchParams;
  const result = await load(() => provena.scopes());
  if (result.data === null) return <AppShell active="/scopes"><div className="content"><DataState title="Scope topology could not be loaded" message={result.error} tone="danger"/></div></AppShell>;
  const data = result.data;
  let requested: string | undefined;
  try { requested = configuredScope(params.scope); } catch {}
  const selected = data.items.find(item=>item.id === requested) ?? data.items.find(item=>item.kind === "project") ?? data.items[0];
  const roots = data.items.filter(item=>item.kind === "organization");
  const projects = data.items.filter(item=>item.kind === "project");
  const branches = data.items.filter(item=>item.kind === "branch");
  return <AppShell active="/scopes" scopeId={selected?.id}><div className="content scopes-page"><PageHeader eyebrow={<><Code>TENANCY ARCHITECTURE</Code><Badge tone="verified">Organization filtered</Badge></>} title="Scope Hierarchy & Memory Boundaries" description="Inspect real organization, project, and branch scopes and their exact-scope claim counts."/>
    <div className="metrics"><MetricCard label="Total scopes" value={data.items.length}/><MetricCard label="Root organizations" value={roots.length}/><MetricCard label="Branch partitions" value={branches.length} tone="active"/><MetricCard label="Database isolation" value={<span className="enabled">● Organization scoped</span>}/></div>
    {!selected ? <DataState title="No scopes exist" message="Create a project through the Provena API to establish a project scope."/> : <div className="scope-layout"><Panel className="tree"><div className="tree-head"><b>⌘ SCOPE TREE TOPOLOGY</b><span>{data.items.length} nodes</span></div><div className="tree-body">{roots.map(root=><div key={root.id}>⌄　▦　{data.organization.name} <Badge>Root Org</Badge></div>)}{projects.map(project=><div className="tree-project-group" key={project.id}><div className="tree-project">⌄　▣　{project.project_name ?? project.key} <Badge tone="active">Project</Badge><small>{project.claim_total} exact-scope claims</small></div><Link className={`branch ${project.id===selected.id?"selected":""}`} href={`/scopes?scope=${project.id}`}>● <b>{project.key}</b><Badge>Project scope</Badge><small>▣ {project.claim_total} claims　<span>{project.claim_counts.candidate ?? 0} cand.</span>　<b>! {project.claim_counts.conflicted ?? 0} confl.</b></small></Link>{branches.filter(branch=>branch.parent_id===project.id).map(branch=><Link className={`branch ${branch.id===selected.id?"selected":""}`} href={`/scopes?scope=${branch.id}`} key={branch.id}>● <b>{branch.key}</b><Badge>Branch</Badge>{branch.agents.length > 0 && <Code>{branch.agents.length}A</Code>}<small>{branch.claim_total} claims　<span>{branch.claim_counts.candidate ?? 0} cand.</span>　 Created {formatDate(branch.created_at)}</small></Link>)}</div>)}</div><footer><code>scope: {selected.id}</code><CopyButton compact label="Copy ID" value={selected.id}/></footer></Panel>
      <div className="scope-details"><Panel><div className="scope-summary"><div><b>⚙ {data.organization.name} / {selected.project_name ?? selected.key}</b><p>Kind: {selected.kind} · Parent: {selected.parent_id ?? "none"}</p></div><CopyButton label="Copy scope ID" value={selected.id}/></div><div className="scope-stats"><div><span>TOTAL CLAIMS</span><b>{selected.claim_total}</b></div><div><span>CANDIDATE TRIAGE</span><b className="text-amber">{selected.claim_counts.candidate ?? 0} pending</b></div><div><span>CONFLICTED</span><b className="text-conflicted">{selected.claim_counts.conflicted ?? 0} items</b></div><div><span>CREATED</span><b>{formatDate(selected.created_at)}</b></div><div><span>OBSERVED AGENTS</span><b className="link-token">{selected.agents.length}</b></div></div></Panel>
      <Panel><div className="scope-section-title"><h2>♧ Memory Visibility &amp; Write Rules</h2><Code>NOT YET MODELED</Code></div><div className="policy-list"><div><b>Exact-scope query behavior <Badge tone="verified">Enforced</Badge></b><p>Current retrieval and operator APIs require an explicit scope ID and do not merge peer scopes.</p></div><div><b>Branch inheritance policy <Badge>Unavailable</Badge></b><p>No durable inheritance policy record exists yet, so the console does not infer one.</p></div></div></Panel>
      <Panel><div className="scope-section-title"><h2><Bot size={18}/>Agents Observed in Scope</h2><Code>{selected.agents.length} FROM SESSIONS</Code></div>{selected.agents.length ? <table className="data-table agent-table"><thead><tr><th>Agent identity</th><th>Recorded sessions</th><th>Last observed</th></tr></thead><tbody>{selected.agents.map(agent=><tr key={agent.id}><td><span className="agent-icon">{agent.name.slice(0,2).toUpperCase()}</span><b>{agent.name}</b></td><td>{agent.session_count}</td><td>{formatDate(agent.last_active)}</td></tr>)}</tbody></table> : <DataState title="No named agents in this scope" message="Sessions without an agent identity are intentionally not attributed."/>}</Panel>
      <Panel><div className="scope-section-title"><h2>→ Branch Diff &amp; Sync Status</h2><Code>NOT RECORDED</Code></div><div className="notice"><LockKeyhole size={18}/><span>Cross-branch diff and promotion are not implemented. No synchronization status is inferred from claim counts.</span></div></Panel></div></div>}
  </div></AppShell>;
}
