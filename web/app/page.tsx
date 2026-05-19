"use client";

import Link from "next/link";
import { usePoll } from "../components/usePoll";

interface Overview {
  session: { clock: string; day_number: number };
  modules: {
    reconciliation: { open_breaks: number; value_at_risk: number; match_rate: number };
    reporting: { total_aum: number; mandates: number };
    data_quality: { avg_score: number; open_issues: number; degraded: number };
    documents: { processed_today: number };
    ledger: { trades_posted: number; net_income: number; balanced: boolean };
  };
}

function money(n: number): string {
  if (Math.abs(n) >= 1e9) return `$${(n / 1e9).toFixed(2)}B`;
  if (Math.abs(n) >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
  if (Math.abs(n) >= 1e3) return `$${(n / 1e3).toFixed(0)}K`;
  return `$${n.toFixed(0)}`;
}

export default function OverviewPage() {
  const { data, error } = usePoll<Overview>("/api/overview", 4000);

  return (
    <>
      <div className="page-header">
        <span className="eyebrow">Investment Operations</span>
        <h1 className="page-title">Operations Control Centre</h1>
        <p className="page-sub">
          A live back-office platform — five operations modules running over one
          continuously evolving market simulation, anchored to real FRED data.
        </p>
      </div>

      {error && <div className="error-strip">Could not reach the suite API — {error}</div>}
      {!data && !error && (
        <div className="loading-row">
          <span className="spinner" /> Connecting to operations feed…
        </div>
      )}

      {data && (
        <>
          <div className="mod-grid">
            <Link href="/reconciliation" className="mod-card">
              <div className="mod-card-name">Reconciliation</div>
              <div className="mod-card-stat">{data.modules.reconciliation.open_breaks}</div>
              <div className="mod-card-desc">
                open breaks · {money(data.modules.reconciliation.value_at_risk)} at risk ·{" "}
                {(data.modules.reconciliation.match_rate * 100).toFixed(1)}% matched
              </div>
            </Link>
            <Link href="/reporting" className="mod-card">
              <div className="mod-card-name">Reporting</div>
              <div className="mod-card-stat">{money(data.modules.reporting.total_aum)}</div>
              <div className="mod-card-desc">
                assets under management · {data.modules.reporting.mandates} mandates
              </div>
            </Link>
            <Link href="/data-quality" className="mod-card">
              <div className="mod-card-name">Data Quality</div>
              <div className="mod-card-stat">{data.modules.data_quality.avg_score}</div>
              <div className="mod-card-desc">
                avg feed score · {data.modules.data_quality.open_issues} open issues ·{" "}
                {data.modules.data_quality.degraded} degraded
              </div>
            </Link>
            <Link href="/documents" className="mod-card">
              <div className="mod-card-name">Documents</div>
              <div className="mod-card-stat">{data.modules.documents.processed_today}</div>
              <div className="mod-card-desc">documents processed this session</div>
            </Link>
            <Link href="/ledger" className="mod-card">
              <div className="mod-card-name">Ledger</div>
              <div className="mod-card-stat">{data.modules.ledger.trades_posted}</div>
              <div className="mod-card-desc">
                trades posted · net income {money(data.modules.ledger.net_income)} ·{" "}
                {data.modules.ledger.balanced ? "books balanced" : "out of balance"}
              </div>
            </Link>
          </div>

          <div className="footer">
            <span>
              Investment Operations Suite · session clock {data.session.clock} ·
              day {data.session.day_number}
            </span>
            <span>FastAPI · Next.js · live simulation · FRED · djkimlab.com</span>
          </div>
        </>
      )}
    </>
  );
}
