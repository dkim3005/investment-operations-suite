"use client";

import { useState } from "react";
import { usePoll } from "../../components/usePoll";

interface Line {
  code: string;
  name: string;
  debit: number;
  credit: number;
}

interface Entry {
  entry_id: string;
  ref: string;
  narrative: string;
  lines: Line[];
}

interface TrialRow {
  account_code: string;
  account_name: string;
  account_type: string;
  debit: number;
  credit: number;
}

interface Ledger {
  journal: Entry[];
  journal_total: number;
  trial_balance: TrialRow[];
  pnl: {
    realized_gain: number;
    commission_expense: number;
    fee_expense: number;
    net_income: number;
  };
  summary: {
    trades_posted: number;
    journal_entries: number;
    total_debits: number;
    total_credits: number;
    balanced: boolean;
    ending_cash: number;
  };
}

function money(n: number): string {
  return `$${n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}
function short(n: number): string {
  if (Math.abs(n) >= 1e6) return `$${(n / 1e6).toFixed(2)}M`;
  if (Math.abs(n) >= 1e3) return `$${(n / 1e3).toFixed(0)}K`;
  return `$${n.toFixed(0)}`;
}

export default function LedgerPage() {
  const { data, error } = usePoll<Ledger>("/api/ledger", 4000);
  const [tab, setTab] = useState<"journal" | "trial" | "pnl">("journal");

  return (
    <>
      <div className="page-header">
        <span className="eyebrow">Module · Ledger</span>
        <h1 className="page-title">Trade-to-Ledger Accounting</h1>
        <p className="page-sub">
          Trades post to a double-entry general ledger as the session runs —
          journal, trial balance and income statement, always balanced.
        </p>
      </div>

      {error && <div className="error-strip">API error — {error}</div>}
      {!data && !error && (
        <div className="loading-row"><span className="spinner" /> Posting journal…</div>
      )}

      {data && (
        <>
          <div className="error-strip" style={{
            background: data.summary.balanced ? "rgba(34,197,94,0.07)" : undefined,
            borderColor: data.summary.balanced ? "rgba(34,197,94,0.25)" : undefined,
            color: data.summary.balanced ? "var(--green)" : undefined,
          }}>
            {data.summary.balanced ? "✓" : "✗"} Books balanced — debits{" "}
            {money(data.summary.total_debits)} = credits {money(data.summary.total_credits)}
          </div>

          <div className="metrics">
            <div className="metric">
              <div className="metric-label">Trades Posted</div>
              <div className="metric-value">{data.summary.trades_posted}</div>
              <div className="metric-sub">{data.summary.journal_entries} journal entries</div>
            </div>
            <div className="metric">
              <div className="metric-label">Ending Cash</div>
              <div className="metric-value accent">{short(data.summary.ending_cash)}</div>
              <div className="metric-sub">general ledger</div>
            </div>
            <div className="metric">
              <div className="metric-label">Net Income</div>
              <div className={`metric-value ${data.pnl.net_income >= 0 ? "green" : "red"}`}>
                {short(data.pnl.net_income)}
              </div>
              <div className="metric-sub">session to date</div>
            </div>
            <div className="metric">
              <div className="metric-label">Realized Gain</div>
              <div className={`metric-value ${data.pnl.realized_gain >= 0 ? "green" : "red"}`}>
                {short(data.pnl.realized_gain)}
              </div>
              <div className="metric-sub">on disposals</div>
            </div>
          </div>

          <div className="chips">
            <button className={`chip${tab === "journal" ? " active" : ""}`}
              onClick={() => setTab("journal")}>Journal</button>
            <button className={`chip${tab === "trial" ? " active" : ""}`}
              onClick={() => setTab("trial")}>Trial Balance</button>
            <button className={`chip${tab === "pnl" ? " active" : ""}`}
              onClick={() => setTab("pnl")}>Income Statement</button>
          </div>

          {tab === "journal" && (
            <div className="panel">
              <div className="panel-title">
                General Journal — most recent {data.journal.length} of {data.journal_total}
              </div>
              {[...data.journal].reverse().map((je) => (
                <div className="je" key={je.entry_id}>
                  <div className="je-head">
                    <span className="je-id">{je.entry_id}</span>
                    <span className="je-narr">{je.narrative}</span>
                    <span className="je-ref">{je.ref}</span>
                  </div>
                  <table className="je-lines">
                    <tbody>
                      {je.lines.map((ln, i) => (
                        <tr key={i}>
                          <td className="muted" style={{ width: 50 }}>{ln.code}</td>
                          <td className={ln.credit > 0 ? "je-indent" : ""}>{ln.name}</td>
                          <td className="num">{ln.debit > 0 ? money(ln.debit) : ""}</td>
                          <td className="num" style={{ color: "var(--accent)" }}>
                            {ln.credit > 0 ? money(ln.credit) : ""}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ))}
            </div>
          )}

          {tab === "trial" && (
            <div className="panel">
              <div className="panel-title">Trial Balance</div>
              <table>
                <thead>
                  <tr><th>Code</th><th>Account</th><th>Type</th>
                    <th className="num">Debit</th><th className="num">Credit</th></tr>
                </thead>
                <tbody>
                  {data.trial_balance.map((r) => (
                    <tr key={r.account_code}>
                      <td className="muted">{r.account_code}</td>
                      <td>{r.account_name}</td>
                      <td className="muted">{r.account_type}</td>
                      <td className="num">{r.debit > 0 ? money(r.debit) : "—"}</td>
                      <td className="num" style={{ color: "var(--accent)" }}>
                        {r.credit > 0 ? money(r.credit) : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {tab === "pnl" && (
            <div className="panel">
              <div className="panel-title">Income Statement — session to date</div>
              <div className="kv-row">
                <span className="muted">Realized gain / loss</span>
                <span className={data.pnl.realized_gain >= 0 ? "pos" : "neg"}>
                  {money(data.pnl.realized_gain)}
                </span>
              </div>
              <div className="kv-row">
                <span className="muted">Commission expense</span>
                <span className="neg">({money(data.pnl.commission_expense)})</span>
              </div>
              <div className="kv-row">
                <span className="muted">Management fee expense</span>
                <span className="neg">({money(data.pnl.fee_expense)})</span>
              </div>
              <div className="kv-row" style={{ fontWeight: 700, fontSize: 15 }}>
                <span>Net Income</span>
                <span className={data.pnl.net_income >= 0 ? "pos" : "neg"}>
                  {money(data.pnl.net_income)}
                </span>
              </div>
            </div>
          )}
        </>
      )}
    </>
  );
}
