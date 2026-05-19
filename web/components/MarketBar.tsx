"use client";

import { usePoll } from "./usePoll";

interface Ctx {
  session: {
    clock: string;
    session_date: string;
    day_number: number;
    phase: string;
    tick: number;
  };
  fred: {
    usd_cad: { value: number; date: string } | null;
    treasury_10y: { value: number; date: string } | null;
  };
  top_movers: {
    security: string;
    name: string;
    price: number;
    change_pct: number;
  }[];
}

export default function MarketBar() {
  const { data } = usePoll<Ctx>("/api/market/context", 5000);

  if (!data) {
    return (
      <div className="market-bar">
        <span className="mb-item">connecting to market…</span>
      </div>
    );
  }

  return (
    <div className="market-bar">
      <span className="mb-live">
        <span className="mb-dot" />
        Live
      </span>
      <span className="mb-clock">{data.session.clock}</span>
      <span className="mb-item">
        {data.session.session_date} · Day {data.session.day_number} ·{" "}
        {data.session.phase}
      </span>
      <span className="mb-sep">|</span>
      {data.top_movers.slice(0, 3).map((m) => (
        <span className="mb-mover" key={m.security}>
          {m.security}{" "}
          <span className={m.change_pct >= 0 ? "mb-up" : "mb-down"}>
            {m.change_pct >= 0 ? "▲" : "▼"}
            {Math.abs(m.change_pct * 100).toFixed(2)}%
          </span>
        </span>
      ))}
      <span className="mb-fred">
        FRED · USD/CAD <b>{data.fred.usd_cad?.value ?? "—"}</b> · UST 10Y{" "}
        <b>{data.fred.treasury_10y?.value ?? "—"}%</b>
      </span>
    </div>
  );
}
