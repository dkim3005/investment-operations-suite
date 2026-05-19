"use client";

import { useEffect, useState } from "react";
import { usePoll } from "../../components/usePoll";

interface Sample {
  id: string;
  label: string;
  text: string;
}

interface Field {
  field: string;
  value: string;
  confidence: number;
}

interface Extraction {
  fields: Field[];
  summary: {
    fields_extracted: number;
    fields_expected: number;
    completeness: number;
    avg_confidence: number;
  };
  validations: { name: string; passed: boolean; detail: string }[];
}

interface SopResult {
  id: string;
  title: string;
  content: string;
  relevance: number;
}

interface Info {
  samples: Sample[];
  sops: { id: string; title: string }[];
  processed_today: number;
}

const EXAMPLE_QS = [
  "What do I do when a trade fails to settle?",
  "How is the daily NAV reconciled?",
  "Who can approve an outgoing wire?",
];

export default function DocumentsPage() {
  const { data: info } = usePoll<Info>("/api/documents/info", 6000);
  const [tab, setTab] = useState<"extract" | "sop">("extract");

  // extraction state
  const [text, setText] = useState("");
  const [activeSample, setActiveSample] = useState<string | null>(null);
  const [result, setResult] = useState<Extraction | null>(null);
  const [exLoading, setExLoading] = useState(false);

  // sop state
  const [question, setQuestion] = useState("");
  const [sopResults, setSopResults] = useState<SopResult[] | null>(null);
  const [sopLoading, setSopLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (info && info.samples.length && !text && activeSample === null) {
      setText(info.samples[0].text);
      setActiveSample(info.samples[0].id);
    }
  }, [info, text, activeSample]);

  const extract = async () => {
    if (!text.trim()) return;
    setExLoading(true);
    setError(null);
    setResult(null);
    try {
      const r = await fetch("/api/documents/extract", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setResult(await r.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : "extraction failed");
    } finally {
      setExLoading(false);
    }
  };

  const ask = async (q: string) => {
    if (!q.trim()) return;
    setSopLoading(true);
    setError(null);
    try {
      const r = await fetch("/api/documents/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const d = await r.json();
      setSopResults(d.results);
    } catch (e) {
      setError(e instanceof Error ? e.message : "search failed");
    } finally {
      setSopLoading(false);
    }
  };

  return (
    <>
      <div className="page-header">
        <span className="eyebrow">Module · Documents</span>
        <h1 className="page-title">Document Intelligence</h1>
        <p className="page-sub">
          Structured extraction from trade confirmations and a retrieval
          assistant over the operations procedure library —{" "}
          {info ? `${info.processed_today} documents processed this session.` : "…"}
        </p>
      </div>

      <div className="chips">
        <button className={`chip${tab === "extract" ? " active" : ""}`}
          onClick={() => setTab("extract")}>Trade Confirmation Extraction</button>
        <button className={`chip${tab === "sop" ? " active" : ""}`}
          onClick={() => setTab("sop")}>SOP Assistant</button>
      </div>

      {error && <div className="error-strip">{error}</div>}

      {tab === "extract" && (
        <>
          <div className="panel">
            <div className="panel-title">Trade Confirmation</div>
            <div className="chips">
              {info?.samples.map((s) => (
                <button key={s.id} className={`chip${activeSample === s.id ? " active" : ""}`}
                  onClick={() => { setText(s.text); setActiveSample(s.id); setResult(null); }}>
                  {s.label}
                </button>
              ))}
            </div>
            <textarea value={text} onChange={(e) => { setText(e.target.value); setActiveSample(null); }}
              placeholder="Paste a broker trade confirmation…" />
            <button className="run-btn" onClick={extract} disabled={exLoading || !text.trim()}>
              {exLoading ? "Extracting…" : "Extract Fields"}
            </button>
          </div>

          {result && (
            <div className="panel">
              <div className="panel-title">
                Extracted Fields — {result.summary.fields_extracted}/
                {result.summary.fields_expected} ·{" "}
                {(result.summary.avg_confidence * 100).toFixed(0)}% avg confidence
              </div>
              <table>
                <thead><tr><th>Field</th><th>Value</th><th className="num">Confidence</th></tr></thead>
                <tbody>
                  {result.fields.map((f) => (
                    <tr key={f.field}>
                      <td className="muted">{f.field}</td>
                      <td>{f.value}</td>
                      <td className="num">{(f.confidence * 100).toFixed(0)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {result.validations.map((v) => (
                <div key={v.name} className="kv-row">
                  <span className={v.passed ? "pos" : "neg"}>
                    {v.passed ? "✓" : "✗"} {v.name}
                  </span>
                  <span className="muted" style={{ fontSize: 11.5 }}>{v.detail}</span>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {tab === "sop" && (
        <>
          <div className="panel">
            <div className="panel-title">Operations SOP Assistant</div>
            <div className="ask-row">
              <input type="text" value={question} placeholder="Ask about an operations procedure…"
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && ask(question)} />
              <button className="run-btn" onClick={() => ask(question)}
                disabled={sopLoading || !question.trim()}>
                {sopLoading ? "…" : "Ask"}
              </button>
            </div>
            <div className="chips" style={{ marginTop: 14, marginBottom: 0 }}>
              {EXAMPLE_QS.map((q) => (
                <button key={q} className="chip"
                  onClick={() => { setQuestion(q); ask(q); }}>{q}</button>
              ))}
            </div>
          </div>

          {sopResults && (
            <div className="panel">
              <div className="panel-title">Matched Procedures</div>
              {sopResults.map((r) => (
                <div key={r.id} className="kv-row" style={{ display: "block" }}>
                  <div>
                    <span className="mono-id">{r.id}</span> · <b>{r.title}</b>{" "}
                    <span className="muted" style={{ fontSize: 11 }}>
                      (relevance {r.relevance.toFixed(3)})
                    </span>
                  </div>
                  <div className="muted" style={{ fontSize: 11.5, marginTop: 4 }}>
                    {r.content}
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </>
  );
}
