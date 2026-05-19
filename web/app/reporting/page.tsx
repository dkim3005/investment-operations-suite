"use client";

import { useEffect, useState } from "react";
import { usePoll } from "../../components/usePoll";

interface Mandate {
  id: string;
  name: string;
  benchmark: string;
  fee_bps: number;
  nav: number;
}

interface Report {
  mandate: Mandate;
  nav: number;
  day_change_pct: number;
  performance: { return_1d: number; return_ytd: number };
  allocation: { asset_class: string; market_value: number; weight: number }[];
  top_holdings: { security: string; name: string; market_value: number; weight: number }[];
  fees: { fee_bps: number; monthly_accrual: number };
  holdings_count: number;
}

function money(n: number): string {
  if (Math.abs(n) >= 1e9) return `$${(n / 1e9).toFixed(3)}B`;
  if (Math.abs(n) >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
  return `$${n.toFixed(0)}`;
}
function signed(n: number): string {
  return `${n >= 0 ? "+" : ""}${(n * 100).toFixed(3)}%`;
}

export default function ReportingPage() {
  const { data: mandates } = usePoll<Mandate[]>("/api/reporting/mandates", 6000);
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    if (mandates && mandates.length && !selected) setSelected(mandates[0].id);
  }, [mandates, selected]);

  const { data: report } = usePoll<Report>(
    selected ? `/api/reporting/report/${selected}` : "/api/reporting/mandates",
    4000
  );

  return (
    <>
      <div className="page-header">
        <span className="eyebrow">Module · Reporting</span>
        <h1 className="page-title">Mandate Reporting</h1>
        <p className="page-sub">
          Net asset value, performance, allocation and fee accrual — recomputed
          live as prices move.
        </p>
      </div>

      <div className="chips">
        {mandates?.map((m) => (
          <button key={m.id} className={`chip${selected === m.id ? " active" : ""}`}
            onClick={() => setSelected(m.id)}>
            {m.id} · {money(m.nav)}
          </button>
        ))}
      </div>

      {!report && (
        <div className="loading-row"><span className="spinner" /> Generating report…</div>
      )}

      {report && selected === report.mandate.id && (
        <>
          <div className="metrics">
            <div className="metric">
              <div className="metric-label">Net Asset Value</div>
              <div className="metric-value accent">{money(report.nav)}</div>
              <div className="metric-sub">{report.holdings_count} equity holdings</div>
            </div>
            <div className="metric">
              <div className="metric-label">Session Change</div>
              <div className={`metric-value ${report.day_change_pct >= 0 ? "green" : "red"}`}>
                {signed(report.day_change_pct)}
              </div>
              <div className="metric-sub">since last tick</div>
            </div>
            <div className="metric">
              <div className="metric-label">YTD Return</div>
              <div className={`metric-value ${report.performance.return_ytd >= 0 ? "green" : "red"}`}>
                {signed(report.performance.return_ytd)}
              </div>
              <div className="metric-sub">{report.mandate.benchmark}</div>
            </div>
            <div className="metric">
              <div className="metric-label">Mgmt Fee Accrual</div>
              <div className="metric-value">{money(report.fees.monthly_accrual)}</div>
              <div className="metric-sub">monthly · {report.fees.fee_bps} bps</div>
            </div>
          </div>

          <div className="panel-grid">
            <div className="panel">
              <div className="panel-title">Asset Allocation</div>
              {report.allocation.map((a) => (
                <div className="bar-row" key={a.asset_class}>
                  <span className="bar-name">{a.asset_class}</span>
                  <div className="bar-track">
                    <div className="bar-fill" style={{ width: `${a.weight * 100}%` }} />
                  </div>
                  <span className="bar-val">{(a.weight * 100).toFixed(1)}%</span>
                </div>
              ))}
            </div>
            <div className="panel">
              <div className="panel-title">Top Holdings</div>
              <table>
                <thead>
                  <tr><th>Security</th><th className="num">Market Value</th><th className="num">Weight</th></tr>
                </thead>
                <tbody>
                  {report.top_holdings.map((h) => (
                    <tr key={h.security}>
                      <td>{h.security}
                        <div className="muted" style={{ fontSize: 10.5 }}>{h.name}</div>
                      </td>
                      <td className="num">{money(h.market_value)}</td>
                      <td className="num">{(h.weight * 100).toFixed(2)}%</td>
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
