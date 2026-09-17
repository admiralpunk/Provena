import Link from "next/link";
import { AppShell } from "@/components/shell";
import { Badge, Button, Code, DataState, PageHeader, Panel } from "@/components/ui";
import { configuredScope, load, provena } from "@/lib/provena/server";
import { formatDate } from "@/lib/provena/view-models";
import { Search, ShieldCheck, TerminalSquare } from "lucide-react";

export const metadata = { title: "Integrations" };
export const dynamic = "force-dynamic";

type Tab = "all" | "agents" | "credentials" | "models";

export default async function IntegrationsPage({ searchParams }: { searchParams: Promise<{ scope?: string; tab?: string; q?: string }> }) {
  const params = await searchParams;
  const tab: Tab = ["agents", "credentials", "models"].includes(params.tab ?? "") ? params.tab as Tab : "all";
  const query = params.q?.trim().toLowerCase() ?? "";
  let scopeId: string | undefined;
  try { scopeId = configuredScope(params.scope); } catch {}
  const result = await load(() => provena.integrations());
  if (result.data === null) return <AppShell active="/integrations" scopeId={scopeId}><div className="content"><DataState title="Integration records could not be loaded" message={result.error} tone="danger"/></div></AppShell>;
  const data = result.data;
  const extractionModels = [...new Map(data.extractions.map(run => [`${run.extractor_model}:${run.embedding_model}`, run])).values()];
  const agents = data.agents.filter(item => !query || item.name.toLowerCase().includes(query));
  const credentials = data.credentials.filter(item => !query || `${item.label} ${item.role}`.toLowerCase().includes(query));
  const models = extractionModels.filter(item => !query || `${item.extractor_model} ${item.embedding_model}`.toLowerCase().includes(query));
  const visibleCount = tab === "agents" ? agents.length : tab === "credentials" ? credentials.length : tab === "models" ? models.length : agents.length + credentials.length + models.length;
  const href = (nextTab: Tab) => `/integrations?${new URLSearchParams({ ...(scopeId ? { scope: scopeId } : {}), tab: nextTab, ...(params.q ? { q: params.q } : {}) })}`;
  return <AppShell active="/integrations" scopeId={scopeId}><div className="content integrations-page"><PageHeader eyebrow={<span>TOPOLOGY &amp; IDENTITY　/　<b className="link-token">{data.agents.length} agents recorded</b></span>} title="Integrations & Agent Connections" description="Inspect persisted agent identities, credential metadata, sessions, and extraction runtimes without exposing raw keys." actions={scopeId ? <Link className="button button-secondary" href={`/audit?scope=${scopeId}`}><TerminalSquare size={14}/>View audit log</Link> : undefined}/>
    <div className="integration-tabs" role="navigation" aria-label="Integration types"><Link className={tab === "all" ? "active" : ""} href={href("all")}>All <Code>{data.agents.length + data.credentials.length + extractionModels.length}</Code></Link><Link className={tab === "agents" ? "active" : ""} href={href("agents")}>AI Agents <Code>{data.agents.length}</Code></Link><Link className={tab === "credentials" ? "active" : ""} href={href("credentials")}>Credentials <Code>{data.credentials.length}</Code></Link><Link className={tab === "models" ? "active" : ""} href={href("models")}>Models <Code>{extractionModels.length}</Code></Link><span>RAW KEYS: <b>NEVER RETURNED</b></span><form method="get"><Search size={14}/>{scopeId && <input type="hidden" name="scope" value={scopeId}/>}<input type="hidden" name="tab" value={tab}/><input name="q" defaultValue={params.q} aria-label="Filter integrations" placeholder="Filter integrations..."/><Button compact type="submit">Apply</Button></form></div>
    {!visibleCount && <DataState title="No matching integration metadata" message={query ? "Clear the filter or choose another integration type." : "Create agents, credentials, sessions, or extraction runs through the API."}/>} 
    <div className="integration-grid">{(tab === "all" || tab === "agents") && agents.map(agent=><article className="integration-card" key={agent.id}><header><span className="integration-icon blue">{agent.name.slice(0,2).toUpperCase()}</span><div><h2>{agent.name} <Badge tone={agent.last_active ? "verified" : "neutral"}>{agent.last_active ? "● Observed" : "No sessions"}</Badge></h2><code>Persisted Agent Identity</code></div></header><div className="integration-body"><p>Agent identity recorded by Provena. Capabilities and provider are unavailable unless explicitly modeled.</p><div className="integration-stats"><div><span>SESSIONS</span><b>{agent.session_count}</b></div><div><span>LAST OBSERVED</span><b>{formatDate(agent.last_active)}</b></div><div><span>CREATED</span><b>{formatDate(agent.created_at)}</b></div></div><dl><dt>Agent ID:</dt><dd>{agent.id}</dd><dt>Health:</dt><dd><Code>not recorded</Code></dd><dt>Permissions:</dt><dd><Code>not recorded</Code></dd></dl></div></article>)}
      {(tab === "all" || tab === "credentials") && credentials.map(credential=><article className="integration-card" key={credential.id}><header><span className="integration-icon green">K</span><div><h2>{credential.label} <Badge tone={credential.revoked_at ? "quarantined" : "verified"}>{credential.revoked_at ? "Revoked" : "Valid"}</Badge></h2><code>{credential.role} credential</code></div></header><div className="integration-body"><p>Server-side authentication credential. Only metadata is available after issuance.</p><div className="scope-line">Role: <b>{credential.role}</b></div><dl><dt>Credential ID:</dt><dd>{credential.id}</dd><dt>Created:</dt><dd>{formatDate(credential.created_at)}</dd><dt>Revoked:</dt><dd>{formatDate(credential.revoked_at)}</dd></dl><em>Raw key and hash are omitted from this response.</em></div></article>)}</div>
    {(tab === "all" || tab === "models") && <div className="service-grid">{models.map(run=><Panel key={`${run.extractor_model}:${run.embedding_model}`}><div className="service-head"><span className="integration-icon gray">AI</span><h2>{run.extractor_model} <Badge tone={run.status === "completed" ? "verified" : "conflicted"}>{run.status}</Badge></h2></div><div className="integration-body"><p>Recorded extraction runtime; live daemon health is not inferred.</p><Code>Embedding: {run.embedding_model}</Code><div className="scope-line">Latest recorded run: {formatDate(run.created_at)}</div>{run.error && <div className="notice notice-danger">{run.error}</div>}</div></Panel>)}</div>}
    <div className="notice security-policy"><ShieldCheck size={20}/><div><b>Security &amp; Token Policy</b><p>API keys are displayed only when issued. This operator response contains credential labels, roles, timestamps, and revocation state only.</p></div></div>
  </div></AppShell>;
}
