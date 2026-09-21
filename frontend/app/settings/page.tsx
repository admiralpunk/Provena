import { AppShell } from "@/components/shell";
import { Badge, Code, DataState, PageHeader, Panel, PanelHeader } from "@/components/ui";
import { configuredScope, load, provena } from "@/lib/provena/server";

export const metadata = { title: "Settings" };
export const dynamic = "force-dynamic";

export default async function SettingsPage({ searchParams }: { searchParams: Promise<{ scope?: string }> }) {
  const params = await searchParams;
  let scopeId: string;
  try { scopeId = configuredScope(params.scope); }
  catch (error) { return <AppShell active="/settings"><div className="content"><DataState title="Console scope is not configured" message={(error as Error).message} tone="danger"/></div></AppShell>; }
  const result = await load(() => provena.context(scopeId));
  if (result.data === null) return <AppShell active="/settings" scopeId={scopeId}><div className="content"><DataState title="Settings context could not be loaded" message={result.error} tone="danger"/></div></AppShell>;
  const data = result.data;
  const scope = data.scopes.find(item => item.id === scopeId);
  return <AppShell active="/settings" scopeId={scopeId}><div className="content">
    <PageHeader eyebrow={<Code>READ-ONLY CONFIGURATION</Code>} title="Settings" description="Server-authorized identity and storage guarantees currently exposed by Provena."/>
    <div className="grid-2">
      <Panel><PanelHeader title="OPERATOR CONTEXT" actions={<Badge tone={data.principal.role === "human" ? "verified" : "candidate"}>{data.principal.role}</Badge>}/><div className="panel-body kv-grid"><div className="kv"><label>Organization</label><strong>{data.organization.name}</strong><code>{data.organization.id}</code></div><div className="kv"><label>Credential label</label><strong>{data.principal.label}</strong><code>{data.principal.id}</code></div><div className="kv"><label>Selected scope</label><strong>{scope?.key ?? "Unavailable"}</strong><code>{scopeId}</code></div><div className="kv"><label>Credential storage</label><strong>Server only</strong><p>The browser never receives the Provena API key.</p></div></div></Panel>
      <Panel><PanelHeader title="DURABLE POLICIES" actions={<Code>DATABASE ENFORCED</Code>}/><div className="policy-list"><div><b>Organization isolation <Badge tone="verified">Enforced</Badge></b><p>Tenant-owned reads and foreign keys include the authenticated organization.</p></div><div><b>Immutable evidence <Badge tone="verified">Enforced</Badge></b><p>Events, evidence links, relationships, and memory actions are append-only.</p></div><div><b>Claim proposition <Badge tone="verified">Immutable</Badge></b><p>Subject, predicate, value, and validity timestamps cannot be edited in place.</p></div><div><b>Runtime policy editing <Badge>Not modeled</Badge></b><p>No auditable operator-policy record exists yet, so this screen does not present mutation controls.</p></div></div></Panel>
    </div>
  </div></AppShell>;
}
