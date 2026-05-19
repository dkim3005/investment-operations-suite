"use client";

import { useMemo, useState } from "react";
import { usePoll } from "../../components/usePoll";

interface Feed {
  id: string;
  name: string;
  source: string;
  sla_min: number;
  last_batch_age_min: number;
  quality_score: number;
  status: "healthy" | "watch" | "degraded";
  issue_count: number;
}

interface Issue {
  feed_id: string;
  feed_name: string;
  dimension: string;
  severity: "critical" | "high" | "medium" | "low";
  detail: string;
}

interface DQ {
  summary: {
    feed_count: number;
    avg_quality_score: number;
    total_issues: number;
    feeds_degraded: number;
    by_dimension: Record<string, number>;
  };
  feeds: Feed[];
  issues: Issue[];
}

function scoreColor(s: number): string {
  if (s >= 90) return "#22c55e";
  if (s >= 75) return "#fbbf24";
  return "#f87171";
}

export default function DataQualityPage() {
  const { data, error } = usePoll<DQ>("/api/dataquality", 4000);
  const [feedFilter, setFeedFilter] = useState<string | null>(null);

  const issues = useMemo(
    () => (data ? (feedFilter ? data.issues.filter((i) => i.feed_id === feedFilter) : data.issues) : []),
    [data, feedFilter]
  );

  return (
    <>
      <div className="page-header">
        <span className="eyebrow">Module · Data Quality</span>
        <h1 className="page-title">Feed Quality Monitor</h1>
        <p className="page-sub">
          Live profiling of inbound data feeds — staleness, completeness, and
          accuracy checks updating tick by tick.
        </p>
      </div>

      {error && <div className="error-strip">API error — {error}</div>}
      {!data && !error && (
        <div className="loading-row"><span className="spinner" /> Profiling feeds…</div>
      )}

      {data && (
        <>
          <div className="metrics">
            <div className="metric">
              <div className="metric-label">Feeds Monitored</div>
              <div className="metric-value">{data.summary.feed_count}</div>
              <div className="metric-sub">investment data sources</div>
            </div>
            <div className="metric">
              <div className="metric-label">Avg Quality Score</div>
              <div className="metric-value"
                style={{ color: scoreColor(data.summary.avg_quality_score) }}>
                {data.summary.avg_quality_score}
              </div>
              <div className="metric-sub">0–100 weighted</div>
            </div>
            <div className="metric">
              <div className="metric-label">Open Exceptions</div>
              <div className="metric-value accent">{data.summary.total_issues}</div>
              <div className="metric-sub">across all feeds</div>
            </div>
            <div className="metric">
              <div className="metric-label">Degraded Feeds</div>
              <div className={`metric-value ${data.summary.feeds_degraded > 0 ? "red" : "green"}`}>
                {data.summary.feeds_degraded}
              </div>
              <div className="metric-sub">below 75 score</div>
            </div>
          </div>

          <div className="panel">
            <div className="panel-title">Feed Health</div>
            <div className="feed-grid">
              {data.feeds.map((f) => (
                <div key={f.id} className={`feed-card ${f.status}`}
                  style={{ cursor: "pointer" }}
                  onClick={() => setFeedFilter(feedFilter === f.id ? null : f.id)}>
                  <div className="feed-head">
                    <div>
                      <div className="feed-name">{f.name}</div>
                      <div className="feed-src">{f.source}</div>
                    </div>
                    <div className="feed-score" style={{ color: scoreColor(f.quality_score) }}>
                      {f.quality_score}
                    </div>
                  </div>
                  <div className="feed-bar">
                    <div className="feed-fill"
                      style={{ width: `${f.quality_score}%`, background: scoreColor(f.quality_score) }} />
                  </div>
                  <div className="feed-foot">
                    <span className={`status-${f.status}`}>{f.status}</span>
                    <span>last batch {f.last_batch_age_min}m · {f.issue_count} issue
                      {f.issue_count === 1 ? "" : "s"}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="panel">
            <div className="panel-title">
              Exception Queue ({issues.length})
              {feedFilter && (
                <span className="muted" style={{ cursor: "pointer", marginLeft: 10, fontSize: 11 }}
                  onClick={() => setFeedFilter(null)}>[clear]</span>
              )}
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr><th>Feed</th><th>Dimension</th><th>Severity</th><th>Detail</th></tr>
                </thead>
                <tbody>
                  {issues.map((i, idx) => (
                    <tr key={idx}>
                      <td>{i.feed_name}</td>
                      <td><span className="badge badge-dim">{i.dimension}</span></td>
                      <td><span className={`badge badge-${i.severity}`}>{i.severity}</span></td>
                      <td className="cause">{i.detail}</td>
                    </tr>
                  ))}
                  {issues.length === 0 && (
                    <tr><td colSpan={4} className="muted">No open exceptions — all feeds clean.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </>
  );
}
