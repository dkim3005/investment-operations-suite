"""
Investment Operations Suite — unified back-office platform.
FastAPI on port 13001.

Five modules over one live market simulation:
  reconciliation · reporting · data quality · documents · ledger

Every module reads from market.SIM, a background-advanced trading-day state,
so the suite behaves like a live operations environment.
"""

from __future__ import annotations

import os

# load .env before market.SIM is constructed (it reads FRED_API_KEY)
_envp = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(_envp):
    for _l in open(_envp):
        _l = _l.strip()
        if _l and not _l.startswith("#") and "=" in _l:
            _k, _, _v = _l.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip())

from fastapi import FastAPI, HTTPException                       # noqa: E402
from fastapi.middleware.cors import CORSMiddleware               # noqa: E402
from pydantic import BaseModel                                   # noqa: E402

import documents                                                 # noqa: E402
from market import (SIM, MANDATES, SEC_CLASS, SEC_NAME,           # noqa: E402
                    SIM_MIN_PER_TICK)

app = FastAPI(title="Investment Operations Suite", version="1.0.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"],
    allow_methods=["*"], allow_headers=["*"],
)

RECONCILED_UNIVERSE = 40
PENALTY = {"critical": 14, "high": 8, "medium": 4, "low": 2}


def _sev(impact: float) -> str:
    if impact >= 1_000_000:
        return "critical"
    if impact >= 250_000:
        return "high"
    if impact >= 50_000:
        return "medium"
    return "low"


def _age_label(minutes: int) -> str:
    if minutes < 60:
        return f"{minutes}m"
    return f"{minutes // 60}h {minutes % 60}m"


# ── Health + market context ───────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"status": "ok", "service": "investment-operations-suite"}


@app.get("/api/market/context")
def market_context():
    return SIM.market_context()


# ── Module 1 — Reconciliation ─────────────────────────────────────────────────

def _break_view(b: dict) -> dict:
    px = SIM.prices[b["security"]]
    bt = b["break_type"]
    if bt == "Quantity Break":
        impact = b["diff"] * px
        cust, internal = b["qty"], b["qty"] - b["diff"]
    elif bt == "Market Value Break":
        impact = b["qty"] * px * 0.05
        cust = internal = b["qty"]
    elif bt == "Missing in Internal":
        impact = b["qty"] * px
        cust, internal = b["qty"], None
    elif bt == "Missing in Custodian":
        impact = b["qty"] * px
        cust, internal = None, b["qty"]
    else:  # Cash Break
        impact = b["diff"] * 95.0
        cust = internal = None
    age = (SIM.tick - b["created_tick"]) * SIM_MIN_PER_TICK
    return {
        "id": b["id"], "account": b["account"], "security": b["security"],
        "security_name": b["security_name"], "break_type": bt,
        "custodian_qty": cust, "internal_qty": internal,
        "value_impact": round(impact, 2), "severity": _sev(impact),
        "age_label": _age_label(age),
    }


@app.get("/api/recon")
def recon():
    from market import BREAK_CAUSE
    rows = []
    for b in SIM.breaks:
        v = _break_view(b)
        v["suggested_cause"] = BREAK_CAUSE[b["break_type"]]
        rows.append(v)
    rows.sort(key=lambda r: r["value_impact"], reverse=True)
    breaks = len(rows)
    matched = RECONCILED_UNIVERSE - breaks
    by_sev: dict[str, int] = {}
    by_type: dict[str, int] = {}
    for r in rows:
        by_sev[r["severity"]] = by_sev.get(r["severity"], 0) + 1
        by_type[r["break_type"]] = by_type.get(r["break_type"], 0) + 1
    return {
        "session": SIM.session(),
        "summary": {
            "total_positions": RECONCILED_UNIVERSE,
            "matched": matched, "break_count": breaks,
            "match_rate": round(matched / RECONCILED_UNIVERSE, 4),
            "value_at_risk": round(sum(r["value_impact"] for r in rows), 2),
            "by_severity": by_sev, "by_type": by_type,
        },
        "breaks": rows,
    }


# ── Module 2 — Reporting ──────────────────────────────────────────────────────

def _nav_with(mandate_id: str, prices: dict) -> float:
    h = SIM.holdings[mandate_id]
    eq = sum(prices[s] * q for s, q in h["equity"].items())
    return eq + h["fixed_income"] + h["cash"]


@app.get("/api/reporting/mandates")
def mandates():
    return [{**m, "nav": round(SIM.nav(m["id"]), 2)} for m in MANDATES]


@app.get("/api/reporting/report/{mandate_id}")
def report(mandate_id: str):
    meta = next((m for m in MANDATES if m["id"] == mandate_id), None)
    if meta is None:
        raise HTTPException(status_code=404, detail="mandate not found")
    h = SIM.holdings[mandate_id]
    nav = _nav_with(mandate_id, SIM.prices)
    nav_prev = _nav_with(mandate_id, SIM.prev_prices)
    day_chg = nav / nav_prev - 1 if nav_prev else 0.0

    # allocation by asset class
    buckets: dict[str, float] = {}
    for s, q in h["equity"].items():
        buckets[SEC_CLASS[s]] = buckets.get(SEC_CLASS[s], 0) + SIM.prices[s] * q
    buckets["Fixed Income"] = h["fixed_income"]
    buckets["Cash"] = h["cash"]
    allocation = [
        {"asset_class": c, "market_value": round(v, 2),
         "weight": round(v / nav, 4)}
        for c, v in sorted(buckets.items(), key=lambda x: -x[1])
    ]
    top = sorted(
        ({"security": s, "name": SEC_NAME[s],
          "market_value": round(SIM.prices[s] * q, 2),
          "weight": round(SIM.prices[s] * q / nav, 4)}
         for s, q in h["equity"].items()),
        key=lambda x: -x["market_value"])[:6]
    monthly_fee = nav * meta["fee_bps"] / 10_000 / 12
    return {
        "session": SIM.session(),
        "mandate": meta,
        "nav": round(nav, 2),
        "day_change_pct": round(day_chg, 5),
        "performance": {
            "return_1d": round(day_chg, 5),
            "return_ytd": round(nav / _nav_with(mandate_id,
                                {s: SIM.prices[s] * 0.94 for s in SIM.prices})
                                - 1, 4),
        },
        "allocation": allocation,
        "top_holdings": top,
        "fees": {"fee_bps": meta["fee_bps"],
                 "monthly_accrual": round(monthly_fee, 2)},
        "holdings_count": len(h["equity"]),
    }


# ── Module 3 — Data Quality ───────────────────────────────────────────────────

@app.get("/api/dataquality")
def dataquality():
    feeds, all_issues = [], []
    for fid, f in SIM.feeds.items():
        age = (SIM.tick - f["last_tick"]) * SIM_MIN_PER_TICK
        issues = f["issues"]
        score = max(0, 100 - sum(PENALTY[i["severity"]] for i in issues))
        status = ("healthy" if score >= 90
                  else "watch" if score >= 75 else "degraded")
        for i in issues:
            all_issues.append({**i, "feed_id": fid, "feed_name": f["name"]})
        feeds.append({
            "id": fid, "name": f["name"], "source": f["source"],
            "sla_min": f["sla_min"], "last_batch_age_min": age,
            "quality_score": score, "status": status,
            "issue_count": len(issues),
        })
    by_dim: dict[str, int] = {}
    by_sev: dict[str, int] = {}
    for i in all_issues:
        by_dim[i["dimension"]] = by_dim.get(i["dimension"], 0) + 1
        by_sev[i["severity"]] = by_sev.get(i["severity"], 0) + 1
    avg = round(sum(f["quality_score"] for f in feeds) / len(feeds), 1)
    return {
        "session": SIM.session(),
        "summary": {
            "feed_count": len(feeds), "avg_quality_score": avg,
            "total_issues": len(all_issues),
            "feeds_degraded": sum(1 for f in feeds if f["status"] == "degraded"),
            "by_dimension": by_dim, "by_severity": by_sev,
        },
        "feeds": feeds,
        "issues": sorted(all_issues,
                         key=lambda i: PENALTY[i["severity"]], reverse=True),
    }


# ── Module 4 — Documents ──────────────────────────────────────────────────────

class ExtractRequest(BaseModel):
    text: str


class AskRequest(BaseModel):
    question: str


@app.get("/api/documents/info")
def documents_info():
    return {
        "samples": documents.SAMPLES,
        "sops": [{"id": s["id"], "title": s["title"]} for s in documents.SOPS],
        "processed_today": SIM.docs_processed,
    }


@app.post("/api/documents/extract")
def documents_extract(req: ExtractRequest):
    return documents.extract_fields(req.text)


@app.post("/api/documents/ask")
def documents_ask(req: AskRequest):
    return {"question": req.question, "results": documents.search_sops(req.question)}


# ── Module 5 — Ledger ─────────────────────────────────────────────────────────

COA = {
    "1000": ("Cash", "Asset"), "1100": ("Investments at Cost", "Asset"),
    "3000": ("Contributed Capital", "Equity"),
    "4000": ("Realized Gain / Loss", "Income"),
    "5000": ("Commission Expense", "Expense"),
    "5100": ("Management Fee Expense", "Expense"),
}
OPENING_CASH = 80_000_000.0


@app.get("/api/ledger")
def ledger():
    journal = [{
        "entry_id": "JE-000", "ref": "OPENING",
        "narrative": "Opening balance — capital contribution",
        "lines": [
            {"code": "1000", "name": "Cash", "debit": OPENING_CASH, "credit": 0.0},
            {"code": "3000", "name": "Contributed Capital",
             "debit": 0.0, "credit": OPENING_CASH},
        ],
    }]
    book: dict[str, dict] = {}
    led: dict[str, dict] = {c: {"debit": 0.0, "credit": 0.0} for c in COA}
    for ln in journal[0]["lines"]:
        led[ln["code"]]["debit"] += ln["debit"]
        led[ln["code"]]["credit"] += ln["credit"]

    jid = 1
    for t in SIM.blotter:
        comm = round(t["quantity"] * t["price"] * 0.0001, 2)
        if t["side"] == "BUY":
            cost = round(t["quantity"] * t["price"], 2)
            pos = book.setdefault(t["security"], {"qty": 0, "cost": 0.0})
            pos["qty"] += t["quantity"]
            pos["cost"] += cost
            lines = [
                {"code": "1100", "name": "Investments at Cost",
                 "debit": cost, "credit": 0.0},
                {"code": "5000", "name": "Commission Expense",
                 "debit": comm, "credit": 0.0},
                {"code": "1000", "name": "Cash", "debit": 0.0,
                 "credit": round(cost + comm, 2)},
            ]
            narr = f"Buy {t['quantity']:,} {t['security']} @ {t['price']:.2f}"
        else:
            pos = book.setdefault(t["security"], {"qty": 0, "cost": 0.0})
            avg = pos["cost"] / pos["qty"] if pos["qty"] > 0 else t["price"]
            cost_rel = round(avg * t["quantity"], 2)
            proceeds = round(t["quantity"] * t["price"], 2)
            gain = round(proceeds - cost_rel, 2)
            pos["qty"] -= t["quantity"]
            pos["cost"] -= cost_rel
            lines = [
                {"code": "1000", "name": "Cash",
                 "debit": round(proceeds - comm, 2), "credit": 0.0},
                {"code": "5000", "name": "Commission Expense",
                 "debit": comm, "credit": 0.0},
                {"code": "1100", "name": "Investments at Cost",
                 "debit": 0.0, "credit": cost_rel},
            ]
            if gain >= 0:
                lines.append({"code": "4000", "name": "Realized Gain / Loss",
                              "debit": 0.0, "credit": gain})
            else:
                lines.append({"code": "4000", "name": "Realized Gain / Loss",
                              "debit": -gain, "credit": 0.0})
            narr = (f"Sell {t['quantity']:,} {t['security']} @ "
                    f"{t['price']:.2f} (realized {gain:+,.0f})")
        for ln in lines:
            led[ln["code"]]["debit"] += ln["debit"]
            led[ln["code"]]["credit"] += ln["credit"]
        journal.append({"entry_id": f"JE-{jid:03d}", "ref": t["id"],
                         "narrative": narr, "lines": lines})
        jid += 1

    # management fee accrual scaling with the session
    fee = round(2500.0 * max(1, SIM.tick), 2)
    fee_lines = [
        {"code": "5100", "name": "Management Fee Expense",
         "debit": fee, "credit": 0.0},
        {"code": "1000", "name": "Cash", "debit": 0.0, "credit": fee},
    ]
    for ln in fee_lines:
        led[ln["code"]]["debit"] += ln["debit"]
        led[ln["code"]]["credit"] += ln["credit"]
    journal.append({"entry_id": f"JE-{jid:03d}", "ref": "ACCRUAL",
                     "narrative": "Management fee accrual (session to date)",
                     "lines": fee_lines})

    trial, tdr, tcr = [], 0.0, 0.0
    for code, (name, atype) in COA.items():
        dr, cr = led[code]["debit"], led[code]["credit"]
        bal = dr - cr if atype in ("Asset", "Expense") else cr - dr
        d, c = (bal, 0.0) if bal >= 0 else (0.0, -bal)
        if atype in ("Income", "Equity") and bal >= 0:
            d, c = 0.0, bal
        elif atype in ("Income", "Equity"):
            d, c = -bal, 0.0
        tdr += d
        tcr += c
        trial.append({"account_code": code, "account_name": name,
                      "account_type": atype, "debit": round(d, 2),
                      "credit": round(c, 2)})

    def net(code):
        return led[code]["credit"] - led[code]["debit"]

    realized = net("4000")
    commission = -net("5000")
    fees = -net("5100")
    je_dr = sum(l["debit"] for e in journal for l in e["lines"])
    je_cr = sum(l["credit"] for e in journal for l in e["lines"])
    return {
        "session": SIM.session(),
        "journal": journal[-14:],
        "journal_total": len(journal),
        "trial_balance": trial,
        "pnl": {
            "realized_gain": round(realized, 2),
            "commission_expense": round(commission, 2),
            "fee_expense": round(fees, 2),
            "net_income": round(realized - commission - fees, 2),
        },
        "summary": {
            "trades_posted": len(SIM.blotter),
            "journal_entries": len(journal),
            "total_debits": round(je_dr, 2),
            "total_credits": round(je_cr, 2),
            "balanced": abs(je_dr - je_cr) < 0.5,
            "ending_cash": round(led["1000"]["debit"] - led["1000"]["credit"], 2),
        },
    }


# ── Overview ──────────────────────────────────────────────────────────────────

@app.get("/api/overview")
def overview():
    rec = recon()
    dq = dataquality()
    led = ledger()
    aum = sum(SIM.nav(m["id"]) for m in MANDATES)
    return {
        "session": SIM.session(),
        "modules": {
            "reconciliation": {
                "open_breaks": rec["summary"]["break_count"],
                "value_at_risk": rec["summary"]["value_at_risk"],
                "match_rate": rec["summary"]["match_rate"],
            },
            "reporting": {"total_aum": round(aum, 2), "mandates": len(MANDATES)},
            "data_quality": {
                "avg_score": dq["summary"]["avg_quality_score"],
                "open_issues": dq["summary"]["total_issues"],
                "degraded": dq["summary"]["feeds_degraded"],
            },
            "documents": {"processed_today": SIM.docs_processed},
            "ledger": {
                "trades_posted": led["summary"]["trades_posted"],
                "net_income": led["pnl"]["net_income"],
                "balanced": led["summary"]["balanced"],
            },
        },
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=13001, reload=False)
