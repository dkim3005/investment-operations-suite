"use client";

import { useMemo, useState } from "react";
import { usePoll } from "../../components/usePoll";

interface Brk {
  id: string;
  account: string;
  security: string;
  security_name: string;
  break_type: string;
  custodian_qty: number | null;
  internal_qty: number | null;
  value_impact: number;
  severity: "critical" | "high" | "medium" | "low";
  age_label: string;
  suggested_cause: string;
}

interface Recon {
  summary: {
    total_positions: number;
    matched: number;
    break_count: number;
    match_rate: number;
    value_at_risk: number;
    by_severity: Record<string, number>;
    by_type: Record<string, number>;
  };
  breaks: Brk[];
}

const SEV_COLOR: Record<string, string> = {
  critical: "#f87171", high: "#fb923c", medium: "#fbbf24", low: "#6b8499",
};
const SEV_ORDER = ["critical", "high", "medium", "low"];

function money(n: number): string {
  if (Math.abs(n) >= 1e6) return `$${(n / 1e6).toFixed(2)}M`;
  if (Math.abs(n) >= 1e3) return `$${(n / 1e3).toFixed(0)}K`;
  return `$${n.toFixed(0)}`;
}

export default function ReconciliationPage() {
  const { data, error } = usePoll<Recon>("/api/recon", 4000);
  const [sev, setSev] = useState<string | null>(null);

  const rows = useMemo(
    () => (data ? (sev ? data.breaks.filter((b) => b.severity === sev) : data.breaks) : []),
    [data, sev]
  );

  return (
    <>
      <div className="page-header">
        <span className="eyebrow">Module · Reconciliation</span>
        <h1 className="page-title">Custodian Reconciliation</h1>
        <p className="page-sub">
          Live matching of the custodian feed against the internal book —
          breaks open and clear as the session progresses.
        </p>
      </div>

      {error && <div className="error-strip">API error — {error}</div>}
      {!data && !error && (
        <div className="loading-row"><span className="spinner" /> Reconciling…</div>
      )}

      {data && (
        <>
          <div className="metrics">
            <div className="metric">
              <div className="metric-label">Positions</div>
              <div className="metric-value">{data.summary.total_positions}</div>
              <div className="metric-sub">{data.summary.matched} matched clean</div>
            </div>
            <div className="metric">
              <div className="metric-label">Match Rate</div>
              <div className="metric-value green">
                {(data.summary.match_rate * 100).toFixed(1)}%
              </div>
              <div className="metric-sub">straight-through</div>
            </div>
            <div className="metric">
              <div className="metric-label">Open Breaks</div>
              <div className="metric-value red">{data.summary.break_count}</div>
              <div className="metric-sub">
                {data.summary.by_severity.critical ?? 0} critical
              </div>
            </div>
            <div className="metric">
              <div className="metric-label">Value at Risk</div>
              <div className="metric-value accent">
                {money(data.summary.value_at_risk)}
              </div>
              <div className="metric-sub">aggregate exposure</div>
            </div>
          </div>

          <div className="panel">
            <div className="panel-title">Breaks by Severity</div>
            {SEV_ORDER.map((s) => {
              const count = data.summary.by_severity[s] ?? 0;
              const max = Math.max(1, ...Object.values(data.summary.by_severity));
              return (
                <div className="bar-row" key={s}>
                  <span className="bar-name" style={{ textTransform: "capitalize" }}>
                    {s}
                  </span>
                  <div className="bar-track">
                    <div className="bar-fill"
                      style={{ width: `${(count / max) * 100}%`, background: SEV_COLOR[s] }} />
                  </div>
                  <span className="bar-val">{count}</span>
                </div>
              );
            })}
          </div>

          <div className="panel">
            <div className="panel-title">Break Queue — {rows.length}</div>
            <div className="chips">
              <button className={`chip${sev === null ? " active" : ""}`}
                onClick={() => setSev(null)}>All</button>
              {SEV_ORDER.map((s) => (
                <button key={s} className={`chip${sev === s ? " active" : ""}`}
                  onClick={() => setSev(s)}>
                  {s} ({data.summary.by_severity[s] ?? 0})
                </button>
              ))}
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Break</th><th>Account</th><th>Security</th><th>Type</th>
                    <th className="num">Custodian</th><th className="num">Internal</th>
                    <th className="num">Impact</th><th>Severity</th>
                    <th className="num">Age</th><th>Probable Cause</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((b) => (
                    <tr key={b.id}>
                      <td className="mono-id">{b.id}</td>
                      <td>{b.account}</td>
                      <td>{b.security}</td>
                      <td><span className="badge badge-type">{b.break_type}</span></td>
                      <td className="num">
                        {b.custodian_qty === null ? "—" : b.custodian_qty.toLocaleString()}
                      </td>
                      <td className="num">
                        {b.internal_qty === null ? "—" : b.internal_qty.toLocaleString()}
                      </td>
                      <td className="num">{money(b.value_impact)}</td>
                      <td><span className={`badge badge-${b.severity}`}>{b.severity}</span></td>
                      <td className="num">{b.age_label}</td>
                      <td className="cause">{b.suggested_cause}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </>
  );
}
