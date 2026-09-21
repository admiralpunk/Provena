import { Badge, Code, Progress, type Status } from "./ui";
import type { ClaimRow } from "@/lib/provena/view-models";
import Link from "next/link";

const authorityTone = { Low: "low", Medium: "neutral", High: "high", Ephemeral: "neutral", Unavailable: "neutral" } as const;

export function ClaimTable({ rows }: { rows: ClaimRow[] }) {
  return (
    <div className="table-wrap">
      <table className="data-table claim-table">
        <thead><tr><th>Proposition &amp; deconstructed triple</th><th>Status</th><th>Authority</th><th>Confidence</th><th>Relevance</th></tr></thead>
        <tbody>{rows.map((claim) => <tr key={claim.id} className={claim.status === "superseded" ? "row-muted" : undefined}>
          <td><Link className="claim-title" href={`/memories/${claim.id}`}><span>{claim.title}</span><Code>#{claim.id.slice(0, 8)}</Code>{claim.note && <Badge tone={claim.status === "active" ? "conflicted" : "neutral"}>{claim.note}</Badge>}</Link><span className="claim-triple"><b className="link-token">{claim.subject}</b> . <b>{claim.predicate}</b> = {claim.value}</span></td>
          <td><Badge tone={claim.status as Status}>{claim.status}</Badge></td>
          <td><Badge tone={authorityTone[claim.authority]}>{claim.authority}</Badge></td>
          <td>{claim.confidence === null ? <span className="mono-small">Not recorded</span> : <><span className="mono-small">{claim.confidence}%</span><Progress value={claim.confidence} tone={claim.status === "superseded" ? "gray" : "green"} /></>}</td>
          <td>{claim.relevance ? <><strong className="link-token mono">{claim.relevance}%</strong><div className="mono-small">cos_sim</div></> : <><span>—</span><div className="mono-small">no query</div></>}</td>
        </tr>)}</tbody>
      </table>
    </div>
  );
}
