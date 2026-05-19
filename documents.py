"""
Document intelligence for the suite — trade-confirmation extraction and a
TF-IDF retrieval assistant over the operations SOP knowledge base.
"""

from __future__ import annotations

import math
import re
from collections import Counter

SAMPLES = [
    {"id": "TC-1", "label": "Equity buy — RBC Capital Markets",
     "text": ("TRADE CONFIRMATION\nBroker: RBC Capital Markets\n"
              "Account: GLOBAL-EQUITY (MND-200)\nTrade Date: 2026-05-18\n"
              "Settlement Date: 2026-05-20\n"
              "BUY 12,000 shares of Apple Inc (AAPL)\n"
              "Price: USD 185.40 per share\nGross Amount: USD 2,224,800.00\n"
              "Commission: USD 1,112.40\nNet Amount: USD 2,225,912.40\n"
              "Settlement Currency: USD")},
    {"id": "TC-2", "label": "Equity sell — TD Securities",
     "text": ("TRADE CONFIRMATION\nBroker: TD Securities\n"
              "Account: PENSION-CORE (MND-100)\nTrade Date: 2026-05-18\n"
              "Settlement Date: 2026-05-20\n"
              "SELL 8,500 shares of Enbridge Inc (ENB)\n"
              "Price: CAD 49.30 per share\nGross Amount: CAD 419,050.00\n"
              "Commission: CAD 209.53\nNet Amount: CAD 418,840.47\n"
              "Settlement Currency: CAD")},
    {"id": "TC-3", "label": "Equity buy — BMO Capital Markets",
     "text": ("TRADE CONFIRMATION\nBroker: BMO Capital Markets\n"
              "Account: GROWTH-MANDATE (MND-200)\nTrade Date: 2026-05-18\n"
              "Settlement Date: 2026-05-20\n"
              "BUY 15,000 shares of Microsoft Corp (MSFT)\n"
              "Price: USD 412.20 per share\nGross Amount: USD 6,183,000.00\n"
              "Commission: USD 3,091.50\nNet Amount: USD 6,186,091.50\n"
              "Settlement Currency: USD")},
]

SOPS = [
    {"id": "SOP-01", "title": "Trade Settlement Fails",
     "content": "When a trade fails to settle on the contractual settlement "
                "date, Operations identifies the fail reason — insufficient "
                "securities, insufficient cash, or a standing settlement "
                "instruction mismatch. Contact the custodian and counterparty "
                "within one business day. Failed trades above CAD 1,000,000 "
                "are escalated to the Operations Manager. Track every fail in "
                "the daily fails log until it is resolved."},
    {"id": "SOP-02", "title": "Daily NAV Reconciliation",
     "content": "The internal net asset value is reconciled against the "
                "custodian-reported NAV every business day. Differences within "
                "one basis point are auto-cleared. Larger differences require "
                "investigation of pricing, accruals, and unposted transactions "
                "before sign-off. NAV reconciliation completes before 10:00 ET."},
    {"id": "SOP-03", "title": "Corporate Actions Processing",
     "content": "Mandatory corporate actions such as dividends, stock splits, "
                "and mergers are applied on the ex-date from custodian and "
                "vendor feeds. Voluntary actions require an election before the "
                "broker deadline. Entitlements are reconciled against the "
                "position record on pay-date."},
    {"id": "SOP-04", "title": "Cash Management and Sweeps",
     "content": "Cash sweeps run at end of day. Operations confirms projected "
                "cash against custodian balances, posts income accruals and "
                "management fees, and ensures no account is overdrawn. "
                "Uninvested cash above the threshold is swept to the money "
                "market pool."},
    {"id": "SOP-05", "title": "Pricing Exception Handling",
     "content": "Securities flagged as stale, missing, or outside the tolerance "
                "band are reviewed against an alternate vendor source. A price "
                "override requires Operations Manager approval and is "
                "documented with the source and rationale."},
    {"id": "SOP-06", "title": "Month-End Close",
     "content": "Month-end close produces the management and client report "
                "package after final pricing. The checklist covers final NAV, "
                "performance, fee accrual, and reconciliation sign-off. All "
                "breaks must be cleared or explained before the close is "
                "certified."},
    {"id": "SOP-07", "title": "Wire Transfer Authorization",
     "content": "Outgoing wires require dual authorization — a preparer and an "
                "approver who must be different people. Wire instructions are "
                "verified against the standing settlement instructions on file. "
                "Wires above CAD 5,000,000 require a second-level approval."},
    {"id": "SOP-08", "title": "New Account Onboarding",
     "content": "Onboarding a new mandate sets up the account in the book of "
                "record, registers standing settlement instructions, configures "
                "the data feeds, and runs a parallel reconciliation before "
                "go-live. The account is not activated until a clean "
                "reconciliation is achieved."},
]

_WORD = re.compile(r"[a-z0-9]+")
_STOP = {"the", "a", "an", "is", "are", "to", "of", "and", "in", "on", "for",
         "with", "as", "by", "at", "be", "or", "from", "that", "this", "it",
         "do", "i", "how", "what", "when", "which", "we", "must"}


def _tokens(text: str) -> list[str]:
    return [w for w in _WORD.findall(text.lower()) if w not in _STOP]


def _build_idf(docs):
    df: Counter = Counter()
    for d in docs:
        for t in set(d):
            df[t] += 1
    n = len(docs)
    return {t: math.log((n + 1) / (c + 1)) + 1.0 for t, c in df.items()}


def _vec(tokens, idf):
    tf = Counter(tokens)
    total = len(tokens) or 1
    return {t: (c / total) * idf.get(t, 0.0) for t, c in tf.items()}


def _cosine(a, b):
    common = set(a) & set(b)
    num = sum(a[t] * b[t] for t in common)
    da = math.sqrt(sum(v * v for v in a.values()))
    db = math.sqrt(sum(v * v for v in b.values()))
    return num / (da * db) if da and db else 0.0


_SOP_TOK = [_tokens(s["title"] + " " + s["content"]) for s in SOPS]
_IDF = _build_idf(_SOP_TOK)
_SOP_VEC = [_vec(t, _IDF) for t in _SOP_TOK]


def search_sops(question: str, top_k: int = 3) -> list[dict]:
    qv = _vec(_tokens(question), _IDF)
    scored = sorted(
        ((_cosine(qv, v), s) for s, v in zip(SOPS, _SOP_VEC)),
        key=lambda x: x[0], reverse=True)
    return [{"id": s["id"], "title": s["title"], "content": s["content"],
             "relevance": round(score, 4)} for score, s in scored[:top_k]]


def extract_fields(text: str) -> dict:
    fields: list[dict] = []

    def grab(name, pattern, conf, group=1):
        m = re.search(pattern, text, re.I)
        if m:
            fields.append({"field": name, "value": m.group(group).strip(),
                           "confidence": round(conf, 2)})

    grab("Broker / Counterparty", r"Broker[:\s]+(.+)", 0.97)
    grab("Account", r"Account[:\s]+(.+)", 0.96)
    grab("Trade Date", r"Trade Date[:\s]+(\d{4}-\d{2}-\d{2})", 0.99)
    grab("Settlement Date", r"Settlement Date[:\s]+(\d{4}-\d{2}-\d{2})", 0.99)
    m = re.search(r"\b(BUY|SELL)\s+([\d,]+)\s+shares of\s+(.+?)\s*\(([A-Z0-9.\-]+)\)",
                  text, re.I)
    if m:
        fields.append({"field": "Side", "value": m.group(1).upper(), "confidence": 0.99})
        fields.append({"field": "Quantity", "value": m.group(2).replace(",", ""), "confidence": 0.98})
        fields.append({"field": "Security", "value": m.group(3).strip(), "confidence": 0.95})
        fields.append({"field": "Identifier", "value": m.group(4), "confidence": 0.97})
    grab("Price", r"Price[:\s]+(?:USD|CAD)?\s*([\d,]+\.\d{2})", 0.96)
    grab("Gross Amount", r"Gross Amount[:\s]+(?:USD|CAD)?\s*([\d,]+\.\d{2})", 0.97)
    grab("Commission", r"Commission[:\s]+(?:USD|CAD)?\s*([\d,]+\.\d{2})", 0.95)
    grab("Net Amount", r"Net Amount[:\s]+(?:USD|CAD)?\s*([\d,]+\.\d{2})", 0.97)
    grab("Settlement Currency", r"Settlement Currency[:\s]+([A-Z]{3})", 0.98)

    found = len(fields)
    avg = round(sum(f["confidence"] for f in fields) / found, 3) if found else 0.0
    checks = []
    vals = {f["field"]: f["value"] for f in fields}
    try:
        if {"Quantity", "Price", "Gross Amount"} <= vals.keys():
            q = float(vals["Quantity"])
            p = float(vals["Price"].replace(",", ""))
            g = float(vals["Gross Amount"].replace(",", ""))
            checks.append({"name": "Gross = Quantity × Price",
                           "passed": abs(q * p - g) < max(1.0, g * 0.001),
                           "detail": f"{q:,.0f} × {p:,.2f} = {q * p:,.2f} vs {g:,.2f}"})
    except (ValueError, KeyError):
        pass
    return {"fields": fields,
            "summary": {"fields_extracted": found, "fields_expected": 13,
                        "completeness": round(found / 13, 3), "avg_confidence": avg},
            "validations": checks}
