"""
Live market simulation — the shared state behind the Investment Operations Suite.

A background thread advances a simulated trading day: prices random-walk,
reconciliation breaks open and clear, data feeds tick and go stale, and trades
post to the blotter. Every module reads from this one evolving state, so the
whole suite behaves like a live operations environment rather than a static
snapshot. Real USD/CAD and Treasury data is pulled from FRED as an anchor.
"""

from __future__ import annotations

import json
import os
import random
import threading
import time
import urllib.request
from datetime import datetime, timedelta

# ── Reference data ────────────────────────────────────────────────────────────

SECURITIES = [
    ("RY", "Royal Bank of Canada", 134.10, "Canadian Equity"),
    ("TD", "Toronto-Dominion Bank", 78.55, "Canadian Equity"),
    ("BNS", "Bank of Nova Scotia", 64.75, "Canadian Equity"),
    ("ENB", "Enbridge Inc", 49.30, "Canadian Equity"),
    ("CNQ", "Canadian Natural Resources", 47.85, "Canadian Equity"),
    ("CP", "Canadian Pacific Kansas City", 108.40, "Canadian Equity"),
    ("SHOP", "Shopify Inc", 88.90, "Canadian Equity"),
    ("BCE", "BCE Inc", 44.15, "Canadian Equity"),
    ("AAPL", "Apple Inc", 185.40, "US Equity"),
    ("MSFT", "Microsoft Corp", 412.20, "US Equity"),
    ("JPM", "JPMorgan Chase & Co", 198.70, "US Equity"),
    ("XOM", "Exxon Mobil Corp", 112.30, "US Equity"),
]
SEC_NAME = {s[0]: s[1] for s in SECURITIES}
SEC_CLASS = {s[0]: s[3] for s in SECURITIES}

MANDATES = [
    {"id": "MND-100", "name": "Defined Benefit — Core",
     "benchmark": "60/40 Policy Index", "fee_bps": 28},
    {"id": "MND-200", "name": "Long-Horizon Growth",
     "benchmark": "MSCI ACWI", "fee_bps": 35},
    {"id": "MND-300", "name": "Liability-Driven Fixed Income",
     "benchmark": "FTSE Canada Long Bond", "fee_bps": 18},
    {"id": "MND-400", "name": "Diversified Real Assets",
     "benchmark": "CPI + 4%", "fee_bps": 42},
]
ACCOUNTS = ["PENSION-CORE", "GLOBAL-EQUITY", "FIXED-INCOME-A",
            "GROWTH-MANDATE", "LIABILITY-HEDGE"]

BREAK_TYPES = ["Quantity Break", "Market Value Break",
               "Missing in Internal", "Missing in Custodian", "Cash Break"]
BREAK_CAUSE = {
    "Quantity Break": "Unbooked trade or T+1 settlement timing.",
    "Market Value Break": "Stale or mismatched vendor price snapshot.",
    "Missing in Internal": "Settled at custodian, not yet booked internally.",
    "Missing in Custodian": "Internal trade not yet settled at custodian.",
    "Cash Break": "Unposted income, fee, or FX entry.",
}

FEEDS = [
    {"id": "FEED-PX", "name": "Bloomberg Pricing", "source": "Bloomberg B-PIPE",
     "sla_min": 18},
    {"id": "FEED-FX", "name": "Reuters FX Rates", "source": "Refinitiv Elektron",
     "sla_min": 5},
    {"id": "FEED-POS", "name": "Custodian Positions", "source": "RBC I&TS",
     "sla_min": 30},
    {"id": "FEED-IDX", "name": "Index Constituents", "source": "FTSE Russell",
     "sla_min": 60},
    {"id": "FEED-RAT", "name": "Credit Ratings", "source": "S&P / Moody's",
     "sla_min": 120},
]

TICK_SECONDS = 5            # real seconds per simulated tick
SIM_MIN_PER_TICK = 5        # simulated minutes advanced per tick
DAY_OPEN_MIN = 9 * 60 + 30  # 09:30
DAY_CLOSE_MIN = 16 * 60     # 16:00


def _sev(impact: float) -> str:
    if impact >= 1_000_000:
        return "critical"
    if impact >= 250_000:
        return "high"
    if impact >= 50_000:
        return "medium"
    return "low"


class MarketSim:
    def __init__(self):
        self._lock = threading.RLock()
        self._rng = random.Random(20260518)
        self.tick = 0
        self.prices = {s[0]: s[2] for s in SECURITIES}
        self.prev_prices = dict(self.prices)
        self.breaks: list[dict] = []
        self.feeds: dict[str, dict] = {}
        self.blotter: list[dict] = []
        self.docs_processed = 142
        self._break_seq = 1
        self._trade_seq = 1
        self.fred = {"usd_cad": None, "treasury_10y": None, "fetched": None}

        # fixed mandate holdings (quantities) — NAV moves as prices move
        self.holdings: dict[str, dict] = {}
        for m in MANDATES:
            r = random.Random(sum(ord(c) for c in m["id"]))
            held = r.sample([s[0] for s in SECURITIES], r.randint(7, 10))
            self.holdings[m["id"]] = {
                "equity": {sym: r.randint(20, 260) * 1000 for sym in held},
                "fixed_income": round(r.uniform(80, 900) * 1_000_000, 2),
                "cash": round(r.uniform(2, 40) * 1_000_000, 2),
            }

        for f in FEEDS:
            self.feeds[f["id"]] = {**f, "last_tick": 0, "issues": []}
        self._seed()
        self._fetch_fred()

        threading.Thread(target=self._run, daemon=True).start()
        threading.Thread(target=self._fred_loop, daemon=True).start()

    # ── session clock ─────────────────────────────────────────────────────────

    def session(self) -> dict:
        total = self.tick * SIM_MIN_PER_TICK
        day = total // (DAY_CLOSE_MIN - DAY_OPEN_MIN)
        minute = DAY_OPEN_MIN + total % (DAY_CLOSE_MIN - DAY_OPEN_MIN)
        clock = f"{minute // 60:02d}:{minute % 60:02d}"
        base = datetime(2026, 5, 18) + timedelta(days=int(day))
        return {
            "clock": clock,
            "session_date": base.strftime("%Y-%m-%d"),
            "day_number": int(day) + 1,
            "tick": self.tick,
            "phase": ("pre-open" if minute < DAY_OPEN_MIN + 30
                      else "close" if minute > DAY_CLOSE_MIN - 30
                      else "open"),
        }

    # ── seeding ───────────────────────────────────────────────────────────────

    def _new_break(self):
        rng = self._rng
        account = rng.choice(ACCOUNTS)
        sym = rng.choice([s[0] for s in SECURITIES])
        btype = rng.choice(BREAK_TYPES)
        qty = rng.randint(2, 40) * 1000
        diff = rng.randint(1, 6) * 1000
        b = {
            "id": f"BRK-{self._break_seq:04d}",
            "account": account, "security": sym,
            "security_name": SEC_NAME[sym], "break_type": btype,
            "qty": qty, "diff": diff, "created_tick": self.tick,
        }
        self._break_seq += 1
        return b

    def _new_trade(self):
        rng = self._rng
        sym = rng.choice([s[0] for s in SECURITIES])
        side = rng.choice(["BUY", "SELL"])
        qty = rng.randint(5, 80) * 1000
        t = {
            "id": f"TXN-{self._trade_seq:04d}",
            "tick": self.tick, "side": side, "security": sym,
            "security_name": SEC_NAME[sym], "quantity": qty,
            "price": round(self.prices[sym], 2),
        }
        self._trade_seq += 1
        return t

    def _seed(self):
        for _ in range(7):
            self.breaks.append(self._new_break())
        for _ in range(9):
            self.blotter.append(self._new_trade())
        for fid, f in self.feeds.items():
            f["last_tick"] = -self._rng.randint(0, 4)

    # ── per-tick evolution ────────────────────────────────────────────────────

    def _evolve(self):
        rng = self._rng
        self.prev_prices = dict(self.prices)
        for sym in self.prices:
            self.prices[sym] = round(
                self.prices[sym] * (1 + rng.uniform(-0.0045, 0.0046)), 2)

        # reconciliation breaks open / clear
        if len(self.breaks) > 4 and rng.random() < 0.35:
            self.breaks.pop(rng.randrange(len(self.breaks)))
        if len(self.breaks) < 14 and rng.random() < 0.4:
            self.breaks.append(self._new_break())

        # data feeds receive ticks (reset staleness)
        for fid, f in self.feeds.items():
            if rng.random() < 0.45:
                f["last_tick"] = self.tick
            f["issues"] = self._feed_issues(f)

        # trades post to the blotter
        if rng.random() < 0.4:
            self.blotter.append(self._new_trade())
            self.docs_processed += rng.randint(1, 3)

    def _feed_issues(self, f) -> list[dict]:
        age_min = (self.tick - f["last_tick"]) * SIM_MIN_PER_TICK
        issues = []
        if age_min > f["sla_min"]:
            sev = "high" if age_min > f["sla_min"] * 2 else "medium"
            issues.append({
                "dimension": "Timeliness", "severity": sev,
                "detail": f"Last batch {age_min} min old — exceeds "
                          f"{f['sla_min']} min SLA",
            })
        # deterministic per-feed extra issue, toggled by tick
        h = (self.tick + sum(ord(c) for c in f["id"])) % 7
        if h == 0:
            issues.append({"dimension": "Completeness", "severity": "medium",
                           "detail": "Record count below prior batch"})
        elif h == 3:
            issues.append({"dimension": "Accuracy", "severity": "high",
                           "detail": "Value outside tolerance band"})
        return issues

    def _run(self):
        while True:
            time.sleep(TICK_SECONDS)
            with self._lock:
                self.tick += 1
                self._evolve()

    # ── FRED real-data anchor ─────────────────────────────────────────────────

    def _fetch_fred(self):
        key = os.environ.get("FRED_API_KEY", "")
        if not key:
            return
        for series, field in (("DEXCAUS", "usd_cad"), ("DGS10", "treasury_10y")):
            try:
                url = (f"https://api.stlouisfed.org/fred/series/observations"
                       f"?series_id={series}&api_key={key}&file_type=json"
                       f"&sort_order=desc&limit=1")
                with urllib.request.urlopen(url, timeout=12) as r:
                    obs = json.load(r)["observations"][0]
                self.fred[field] = {"value": float(obs["value"]),
                                    "date": obs["date"]}
            except Exception:
                pass
        self.fred["fetched"] = datetime.now().strftime("%H:%M:%S")

    def _fred_loop(self):
        while True:
            time.sleep(900)
            self._fetch_fred()

    # ── snapshots for the API ─────────────────────────────────────────────────

    def market_context(self) -> dict:
        with self._lock:
            movers = sorted(
                ((s, self.prices[s] / self.prev_prices[s] - 1)
                 for s in self.prices),
                key=lambda x: abs(x[1]), reverse=True)[:4]
            return {
                "session": self.session(),
                "fred": self.fred,
                "top_movers": [
                    {"security": s, "name": SEC_NAME[s],
                     "price": self.prices[s], "change_pct": round(chg, 4)}
                    for s, chg in movers
                ],
            }

    def nav(self, mandate_id: str) -> float:
        h = self.holdings[mandate_id]
        equity = sum(self.prices[s] * q for s, q in h["equity"].items())
        return equity + h["fixed_income"] + h["cash"]


SIM = MarketSim()
