"""
02_compare_vendors.py
---------------------
Deterministic comparison of the standardised quotations.

  * Scores every vendor 0-100 on five criteria (transparent formulas below)
  * Applies the buyer's default weights (editable in config)
  * Runs each vendor against the procurement policy (pass / flag / fail)
  * Ranks vendors and proposes a recommendation - which a human must confirm

No generative AI is used in this file on purpose: the numbers must be
reproducible and auditable. The AI layer (03_ai_assistant.py) only explains
and communicates what this file computes.

Run:  python src/02_compare_vendors.py
Out:  outputs/comparison_results.json
      outputs/comparison_report.md
"""
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"

# ---------------------------------------------------------------- config
DEFAULT_WEIGHTS = {            # must sum to 100
    "cost": 30,
    "technical_fit": 15,
    "delivery": 15,
    "warranty_support": 15,
    "commercial_compliance": 15,
    "past_performance": 10,
}
CRITERIA_LABELS = {
    "cost": "Total cost (USD, all-in)",
    "technical_fit": "Technical fit vs. mandatory specs",
    "delivery": "Delivery lead time",
    "warranty_support": "Warranty and support",
    "commercial_compliance": "Commercial terms and compliance",
    "past_performance": "Past performance (24 months)",
}
WARRANTY_TYPE_POINTS = {"onsite": 30, "depot": 15, "carry-in": 10}


# ---------------------------------------------------------------- scoring
def score_cost(v, all_vendors):
    cheapest = min(x["total_cost_usd"] for x in all_vendors)
    return round(cheapest / v["total_cost_usd"] * 100, 1)


def score_technical(v, req):
    spec = req["mandatory_specs"]
    checks = {
        "ram_gb": (v["ram_gb"] or 0) >= spec["ram_gb"],
        "storage_gb": (v["storage_gb"] or 0) >= spec["storage_gb"],
        "screen_inches": (v["screen_inches"] or 0) >= spec["screen_inches"],
        "os": (v["os"] or "") == spec["os"],
    }
    met = sum(checks.values())
    if met < len(checks):
        return round(met / len(checks) * 60, 1), checks          # missing a mandatory spec caps at 60
    exceeds = (v["ram_gb"] or 0) > spec["ram_gb"] or (v["storage_gb"] or 0) > spec["storage_gb"]
    return (100.0 if exceeds else 90.0), checks


def score_delivery(v, req):
    over = (v["delivery_days_calendar"] or 999) - req["needed_by_days"]
    return 100.0 if over <= 0 else max(0.0, round(100 - 5 * over, 1))


def score_warranty(v, req):
    years = v["effective_warranty_years"] or 0
    if years < req["min_warranty_years"]:
        return 30.0
    return float(70 + WARRANTY_TYPE_POINTS.get(v["warranty_type"], 0))


def score_commercial(v, req):
    pts = 0
    net = v["payment_terms_days"] or 0
    pts += 40 if net >= 45 else 35 if net >= 30 else 15                    # payment terms  (max 40)
    pre = v["prepayment_pct"] or 0
    pts += 30 if pre == 0 else 20 if pre <= req["max_prepayment_pct"] else 0  # prepayment     (max 30)
    pts += 15 if (v["validity_days"] or 0) >= req["min_quote_validity_days"] else 5  # validity (max 15)
    pts += {"yes": 15, "in progress": 5}.get(v["iso27001"], 0)          # ISO 27001      (max 15)
    return float(pts)


def score_performance(v, perf):
    """Past vendor performance. Neutral 60 when there is no history."""
    h = perf["vendors"].get(v["vendor_name"])
    if not h or not h.get("orders_completed"):
        return 60.0, {"history": "none", "orders": 0}
    support = 100 if h["avg_support_response_hours"] <= 8 else 80 if h["avg_support_response_hours"] <= 24 else 60
    score = (h["on_time_delivery_pct"] * 0.4
             + max(0, 100 - h["defect_rate_pct"] * 10) * 0.2
             + h["invoice_accuracy_pct"] * 0.2
             + support * 0.2)
    if h.get("open_disputes"):
        score -= 10 * h["open_disputes"]
    return round(max(0.0, score), 1), {"history": "yes", **{k: h[k] for k in
            ("orders_completed", "on_time_delivery_pct", "defect_rate_pct", "invoice_accuracy_pct", "avg_support_response_hours", "last_order")}}


# ---------------------------------------------------------------- policy
def policy_checks(v, req, n_quotes, perf):
    checks = []

    def add(rule, status, detail):
        checks.append({"rule": rule, "status": status, "detail": detail})

    add("P-01 Three quotations", "pass" if n_quotes >= 3 else "fail", f"{n_quotes} quotations received")

    cap = req["budget_cap_usd"]
    if v["total_cost_usd"] <= cap:
        add("P-02 Budget", "pass", f"USD {v['total_cost_usd']:,.0f} is within the USD {cap:,.0f} cap")
    elif v["total_cost_usd"] <= cap * 1.05:
        add("P-02 Budget", "flag", "Within 5% overrun - CFO re-approval required")
    else:
        add("P-02 Budget", "fail", f"USD {v['total_cost_usd']:,.0f} exceeds the cap by more than 5%")

    pre = v["prepayment_pct"] or 0
    if pre > req["max_prepayment_pct"]:
        add("P-03 Payment terms", "flag", f"{pre}% advance payment exceeds the {req['max_prepayment_pct']}% limit - Finance Director approval needed")
    elif (v["payment_terms_days"] or 0) < 30 and pre == 0:
        add("P-03 Payment terms", "flag", "Terms shorter than Net 30")
    else:
        add("P-03 Payment terms", "pass", f"Net {v['payment_terms_days']} days, {pre}% advance")

    yrs = v["effective_warranty_years"] or 0
    if yrs >= req["min_warranty_years"]:
        note = " (only with the paid extension, already included in cost)" if (v["warranty_years_included"] or 0) < yrs else ""
        add("P-04 Warranty", "pass", f"{yrs}-year {v['warranty_type']} warranty{note}")
    else:
        add("P-04 Warranty", "fail", f"Only {yrs} years offered")

    if req["requires_iso27001"]:
        if v["iso27001"] == "yes":
            add("P-05 Information security", "pass", "ISO 27001 certified")
        elif v["iso27001"] == "in progress":
            add("P-05 Information security", "flag", "ISO 27001 not yet certified - CISO must accept an equivalent or the vendor must not image devices")
        else:
            add("P-05 Information security", "fail", "No ISO 27001 certification")

    if (v["validity_days"] or 0) >= req["min_quote_validity_days"]:
        add("P-06 Quote validity", "pass", f"Valid {v['validity_days']} days")
    else:
        add("P-06 Quote validity", "flag", f"Only {v['validity_days']} days - ask vendor to extend to {req['min_quote_validity_days']}+")

    h = perf["vendors"].get(v["vendor_name"], {})
    if h.get("orders_completed"):
        add("P-08 Vendor history", "pass", f"{h['orders_completed']} orders, {h['on_time_delivery_pct']}% on time, {h['defect_rate_pct']}% defects")
    else:
        add("P-08 Vendor history", "flag", "New vendor with no order history - two trade references and a credit check required before award")
    return checks


# ---------------------------------------------------------------- main
def evaluate(vendors, req, perf, weights=DEFAULT_WEIGHTS):
    assert sum(weights.values()) == 100, "weights must sum to 100"
    results = []
    for v in vendors:
        tech, spec_checks = score_technical(v, req)
        perf_score, perf_detail = score_performance(v, perf)
        scores = {
            "cost": score_cost(v, vendors),
            "technical_fit": tech,
            "delivery": score_delivery(v, req),
            "warranty_support": score_warranty(v, req),
            "commercial_compliance": score_commercial(v, req),
            "past_performance": perf_score,
        }
        weighted = round(sum(scores[k] * weights[k] / 100 for k in weights), 2)
        checks = policy_checks(v, req, len(vendors), perf)
        status = "fail" if any(c["status"] == "fail" for c in checks) else \
                 "flag" if any(c["status"] == "flag" for c in checks) else "pass"
        results.append({
            "vendor_name": v["vendor_name"],
            "quote_ref": v["quote_ref"],
            "total_cost_usd": v["total_cost_usd"],
            "unit_cost_usd_all_in": v["unit_cost_usd_all_in"],
            "delivery_days_calendar": v["delivery_days_calendar"],
            "warranty": f"{v['effective_warranty_years']}-year {v['warranty_type']}",
            "payment": f"Net {v['payment_terms_days']}" if v["payment_terms_days"] else f"{v['prepayment_pct']}% deposit, balance on delivery",
            "iso27001": v["iso27001"],
            "spec_checks": spec_checks,
            "performance": perf_detail,
            "scores": scores,
            "weighted_score": weighted,
            "policy_checks": checks,
            "policy_status": status,
            "extras": v.get("extras", []),
        })

    eligible = [r for r in results if r["policy_status"] != "fail"]
    ranked = sorted(eligible, key=lambda r: r["weighted_score"], reverse=True)
    for i, r in enumerate(ranked, 1):
        r["rank"] = i
    for r in results:
        r.setdefault("rank", None)

    top = ranked[0] if ranked else None
    runner = ranked[1] if len(ranked) > 1 else None
    recommendation = None
    if top:
        conditions = [c["detail"] for c in top["policy_checks"] if c["status"] == "flag"]
        recommendation = {
            "vendor_name": top["vendor_name"],
            "weighted_score": top["weighted_score"],
            "margin_over_runner_up": round(top["weighted_score"] - runner["weighted_score"], 2) if runner else None,
            "runner_up": runner["vendor_name"] if runner else None,
            "conditions": conditions,
            "requires_human_approval": True,
            "key_reasons": build_reasons(top, results),
        }

    return {
        "generated_on": date.today().isoformat(),
        "request_id": req["request_id"],
        "purchasing_category": req["purchasing_category"],
        "quantity": req["quantity"],
        "budget_cap_usd": req["budget_cap_usd"],
        "weights": weights,
        "criteria_labels": CRITERIA_LABELS,
        "vendors": results,
        "recommendation": recommendation,
        "human_review": {
            "status": "pending",
            "note": "System output is a proposal only. A named procurement officer must approve, change, or reject it (policy P-07).",
        },
    }


def build_reasons(top, results):
    reasons = []
    cheapest = min(results, key=lambda r: r["total_cost_usd"])
    if cheapest["vendor_name"] == top["vendor_name"]:
        second = sorted(results, key=lambda r: r["total_cost_usd"])[1]
        reasons.append(f"Lowest all-in cost: USD {top['total_cost_usd']:,.0f}, "
                       f"USD {second['total_cost_usd'] - top['total_cost_usd']:,.0f} below the next vendor")
    else:
        reasons.append(f"Not the cheapest (USD {top['total_cost_usd']:,.0f} vs USD {cheapest['total_cost_usd']:,.0f}) "
                       "but scores higher overall once delivery, warranty and terms are weighed")
    if top["scores"]["delivery"] == 100:
        reasons.append(f"Delivers in {top['delivery_days_calendar']} days, inside the required window")
    if top["scores"]["warranty_support"] >= 100:
        reasons.append(f"Strongest support offer: {top['warranty']}")
    if top["policy_status"] == "pass":
        reasons.append("Passes every procurement policy check with no exceptions needed")
    return reasons


def write_report(res):
    L = []
    L.append(f"# Vendor comparison report — {res['purchasing_category']}")
    L.append(f"Request {res['request_id']} · {res['quantity']} units · budget cap USD {res['budget_cap_usd']:,.0f} · generated {res['generated_on']}\n")
    L.append("## Standardised comparison\n")
    L.append("| Vendor | Total USD | Per unit | Delivery | Warranty | Payment | ISO 27001 | Policy |")
    L.append("|---|---:|---:|---:|---|---|---|---|")
    for v in sorted(res["vendors"], key=lambda r: (r["rank"] is None, r["rank"] or 99)):
        L.append(f"| {v['vendor_name']} | {v['total_cost_usd']:,.0f} | {v['unit_cost_usd_all_in']:,.2f} | {v['delivery_days_calendar']} d | "
                 f"{v['warranty']} | {v['payment']} | {v['iso27001']} | {v['policy_status'].upper()} |")
    L.append("\n## Scores (0-100) and weights\n")
    head = "| Criterion | Weight | " + " | ".join(v["vendor_name"] for v in res["vendors"]) + " |"
    L.append(head)
    L.append("|---|---:|" + "---:|" * len(res["vendors"]))
    for k, label in res["criteria_labels"].items():
        L.append(f"| {label} | {res['weights'][k]}% | " + " | ".join(f"{v['scores'][k]:.0f}" for v in res["vendors"]) + " |")
    L.append("| **Weighted total** | 100% | " + " | ".join(f"**{v['weighted_score']:.1f}**" for v in res["vendors"]) + " |")
    L.append("\n## Previous vendor performance (24 months, fictional)\n")
    L.append("| Vendor | Orders | On time | Defects | Invoice accuracy | Support response |")
    L.append("|---|---:|---:|---:|---:|---:|")
    for v in res["vendors"]:
        p = v["performance"]
        if p["history"] == "yes":
            L.append(f"| {v['vendor_name']} | {p['orders_completed']} | {p['on_time_delivery_pct']}% | {p['defect_rate_pct']}% | {p['invoice_accuracy_pct']}% | {p['avg_support_response_hours']} h |")
        else:
            L.append(f"| {v['vendor_name']} | 0 | — | — | — | — (new vendor) |")
    L.append("\n## Policy checks\n")
    for v in res["vendors"]:
        L.append(f"**{v['vendor_name']}** — {v['policy_status'].upper()}")
        for c in v["policy_checks"]:
            mark = {"pass": "✅", "flag": "⚠️", "fail": "❌"}[c["status"]]
            L.append(f"- {mark} {c['rule']}: {c['detail']}")
        L.append("")
    r = res["recommendation"]
    L.append("## System recommendation (pending human approval)\n")
    L.append(f"**{r['vendor_name']}** — weighted score {r['weighted_score']:.1f}, "
             f"{r['margin_over_runner_up']:.1f} points ahead of {r['runner_up']}.\n")
    for reason in r["key_reasons"]:
        L.append(f"- {reason}")
    if r["conditions"]:
        L.append("\nConditions to clear before approval:")
        for c in r["conditions"]:
            L.append(f"- {c}")
    L.append("\n## How scores are calculated\n")
    L.append("- **Cost**: cheapest all-in total ÷ vendor total × 100 (after FX conversion and adding shipping and any warranty extension needed to reach 3 years).")
    L.append("- **Technical fit**: 90 if every mandatory spec is met, 100 if a spec is exceeded; missing specs cap the score at 60.")
    L.append("- **Delivery**: 100 if within the required window, minus 5 points per day late.")
    L.append("- **Warranty**: 70 base for ≥3 years, plus 30 onsite / 15 depot / 10 carry-in; 30 if under 3 years.")
    L.append("- **Commercial**: payment terms (40) + advance payment (30) + quote validity (15) + ISO 27001 (15).")
    L.append("- **Past performance**: on-time delivery ×0.4 + (100 − defect % ×10) ×0.2 + invoice accuracy ×0.2 + support responsiveness ×0.2, minus 10 per open dispute; a vendor with no history scores a neutral 60 and is flagged for reference checks.")
    L.append("\n_The system never places orders or commits funds. A procurement officer reviews and records the final decision in the dashboard (policy P-07)._")
    (OUT / "comparison_report.md").write_text("\n".join(L))


if __name__ == "__main__":
    req = json.loads((ROOT / "data" / "requirement_intake.json").read_text())
    vendors = json.loads((OUT / "standardised_quotations.json").read_text())
    perf = json.loads((ROOT / "data" / "vendor_performance.json").read_text())
    res = evaluate(vendors, req, perf)
    (OUT / "comparison_results.json").write_text(json.dumps(res, indent=2))
    write_report(res)
    for v in sorted(res["vendors"], key=lambda r: -r["weighted_score"]):
        print(f"#{v['rank']} {v['vendor_name']:28s} score {v['weighted_score']:6.2f}  policy {v['policy_status']}")
    print("recommendation:", res["recommendation"]["vendor_name"], "| conditions:", res["recommendation"]["conditions"] or "none")
    print("wrote outputs/comparison_results.json and comparison_report.md")
