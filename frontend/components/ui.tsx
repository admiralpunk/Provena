import type { ButtonHTMLAttributes, HTMLAttributes, ReactNode } from "react";

export function cx(...values: Array<string | false | null | undefined>) {
  return values.filter(Boolean).join(" ");
}

export type Status = "candidate" | "active" | "verified" | "conflicted" | "superseded" | "quarantined" | "expired" | "ephemeral" | "deleted" | "amber" | "low" | "high" | "neutral";

export function Badge({ children, tone = "neutral", className }: { children: ReactNode; tone?: Status; className?: string }) {
  return <span className={cx("badge", `badge-${tone}`, className)}>{children}</span>;
}

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "danger" | "ghost" | "blue";
  compact?: boolean;
};

export function Button({ variant = "secondary", compact, className, type = "button", ...props }: ButtonProps) {
  return <button type={type} className={cx("button", `button-${variant}`, compact && "button-compact", className)} {...props} />;
}

export function Panel({ children, className, ...props }: HTMLAttributes<HTMLElement>) {
  return <section className={cx("panel", className)} {...props}>{children}</section>;
}

export function PanelHeader({ title, eyebrow, actions }: { title: ReactNode; eyebrow?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="panel-header">
      <div className="panel-title-wrap">{eyebrow}<h2 className="panel-title">{title}</h2></div>
      {actions && <div className="cluster">{actions}</div>}
    </div>
  );
}

export function MetricCard({ label, value, detail, tone = "neutral", icon }: { label: string; value: ReactNode; detail?: ReactNode; tone?: Status; icon?: ReactNode }) {
  return (
    <div className="metric-card">
      <div className="metric-top"><span className="eyebrow">{label}</span>{icon}</div>
      <div className={cx("metric-value", `text-${tone}`)}>{value}</div>
      {detail && <div className="metric-detail">{detail}</div>}
    </div>
  );
}

export function PageHeader({ eyebrow, title, description, actions, badge }: { eyebrow?: ReactNode; title: string; description: string; actions?: ReactNode; badge?: ReactNode }) {
  return (
    <header className="page-heading">
      <div>
        {eyebrow && <div className="page-eyebrow">{eyebrow}</div>}
        <div className="title-row"><h1>{title}</h1>{badge}</div>
        <p>{description}</p>
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </header>
  );
}

export function Progress({ value, tone = "blue" }: { value: number; tone?: "blue" | "green" | "amber" | "gray" }) {
  return <span className="progress" aria-label={`${value}%`}><span className={`progress-${tone}`} style={{ width: `${value}%` }} /></span>;
}

export function Code({ children, className }: { children: ReactNode; className?: string }) {
  return <code className={cx("code", className)}>{children}</code>;
}

export function DataState({ title, message, tone = "neutral" }: { title: string; message: string; tone?: "neutral" | "danger" }) {
  return <section className={cx("data-state", tone === "danger" && "data-state-danger")} role={tone === "danger" ? "alert" : "status"}><span className="eyebrow">{tone === "danger" ? "Data unavailable" : "No records"}</span><h2>{title}</h2><p>{message}</p></section>;
}
