import Image from "next/image";
import Link from "next/link";
import {
  Activity, Blocks, Bot, ChevronDown, CircleAlert, Database,
  FileClock, GitBranch, Grid2X2, Inbox, LockKeyhole, Search, Settings,
  ShieldCheck, SlidersHorizontal, UserRound, Waypoints,
} from "lucide-react";
import type { ReactNode } from "react";
import { cx } from "./ui";
import { load, provena } from "@/lib/provena/server";

const primary = [
  { label: "Overview", href: "/overview", icon: Grid2X2 },
  { label: "Review Inbox", href: "/review", icon: Inbox },
  { label: "Memories", href: "/memories", icon: Waypoints },
  { label: "Conflicts", href: "/conflicts", icon: CircleAlert, danger: true },
  { label: "Retrievals", href: "/retrievals", icon: Activity },
];

const secondary = [
  { label: "Scopes", href: "/scopes", icon: LockKeyhole },
  { label: "Integrations", href: "/integrations", icon: Blocks },
  { label: "Audit Log", href: "/audit", icon: FileClock },
  { label: "Settings", href: "/settings", icon: Settings },
];

function NavItems({ items, active, scopeId }: { items: typeof primary; active: string; scopeId?: string }) {
  return items.map(({ label, href, icon: Icon }) => (
    <Link className={cx("nav-item", active === href && "nav-active")} href={scopeId ? `${href}?scope=${scopeId}` : href} key={href} aria-current={active === href ? "page" : undefined}>
      <span className="nav-label"><Icon size={17} strokeWidth={1.8} /><span>{label}</span></span>
    </Link>
  ));
}

export async function AppShell({ active, children, scopeId: requestedScope }: { active: string; children: ReactNode; scopeId?: string }) {
  const scopeId = requestedScope ?? process.env.PROVENA_SCOPE_ID;
  const context = scopeId ? await load(() => provena.context(scopeId)) : null;
  const data = context?.data;
  const selected = data?.scopes.find((scope) => scope.id === scopeId);
  const project = data?.projects.find((item) => item.id === selected?.project_id);
  const organizationName = data?.organization.name ?? "Organization unavailable";
  const projectName = project?.name ?? "Project unavailable";
  const scopeName = selected?.key ?? "scope unavailable";
  const operatorLabel = data?.principal.label ?? "Console not configured";
  const operatorRole = data?.principal.role ?? "server credential required";
  return (
    <div className="app-shell">
      <header className="topbar">
        <Link href={scopeId ? `/overview?scope=${scopeId}` : "/overview"} className="brand" aria-label="Provena overview">
          <Image src="/logo.svg" width={30} height={30} alt="" priority />
          <strong>Provena</strong><span className="version">v1.4.2-prod</span>
        </Link>
        <span className="top-divider" />
        <Link className="scope-switcher" href={scopeId ? `/scopes?scope=${scopeId}` : "/scopes"}><GitBranch size={15} /><span>{organizationName}</span><b>/</b><span>{projectName}</span><b>/</b><code>{scopeName}</code><ChevronDown size={14} /></Link>
        <form className="global-search" action="/memories" method="get"><Search size={16}/>{scopeId && <input type="hidden" name="scope" value={scopeId}/>}<input name="q" aria-label="Global claim search" placeholder="Search claims and predicates"/><button type="submit">Search</button></form>
        <span className="environment"><i />PRODUCTION</span>
        <span className="top-divider" />
        <div className="operator"><span><b>{operatorLabel}</b><small>{operatorRole}</small></span><span className="avatar"><UserRound size={17} /></span></div>
      </header>
      <aside className="sidebar">
        <div className="nav-section"><span className="nav-heading">Memory Pipeline</span><NavItems items={primary} active={active} scopeId={scopeId} /></div>
        <div className="nav-section"><span className="nav-heading">Governance &amp; Config</span><NavItems items={secondary} active={active} scopeId={scopeId} /></div>
        <div className="engine-status">
          <span className="nav-heading">Telemetry &amp; Engine</span>
          <div><span><Database size={13} />Provena API</span><b>{data ? <><i />connected</> : "unavailable"}</b></div>
          <div><span><Bot size={13} />Extraction runtime</span><b>see integrations</b></div>
          <div className="authority"><span><ShieldCheck size={13} />Boundary</span><code>Organization + scope</code></div>
        </div>
      </aside>
      <main className="workspace">{children}</main>
      <details className="mobile-nav">
        <summary aria-label="Open navigation"><SlidersHorizontal size={20} /></summary>
        <nav className="mobile-nav-panel" aria-label="Mobile navigation">
          <span className="nav-heading">Memory Pipeline</span>
          <NavItems items={primary} active={active} scopeId={scopeId} />
          <span className="nav-heading mobile-nav-heading">Governance &amp; Config</span>
          <NavItems items={secondary} active={active} scopeId={scopeId} />
        </nav>
      </details>
    </div>
  );
}
