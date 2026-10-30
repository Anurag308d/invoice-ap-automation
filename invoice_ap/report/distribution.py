"""Distribution summary of a built dataset: evidence for Evaluation Focus (a)."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal

D = Decimal


def _q(values: list[Decimal], p: int) -> str:
    s = sorted(values)
    return f"{s[min(len(s) - 1, (len(s) * p) // 100)]:.2f}" if s else "-"


def _pct(n: int, d: int) -> str:
    return f"{(D(n) * 100 / D(d)).quantize(D('0.1'))}%" if d else "-"


def summarize(t: dict[str, list[dict[str, str]]]) -> dict:
    out: dict = {}
    pos, lines, gt = t["purchase_order"], t["purchase_order_line"], t.get("ground_truth", [])
    spend = Counter()
    for p in pos:
        spend[p["vendor_id"]] += D(p["total_gross_amount"])
    po_count = Counter(p["vendor_id"] for p in pos)
    goods = [v["vendor_id"] for v in t["vendor"] if v["segment"] == "GOODS"]
    top = max(1, len(goods) // 5)
    ranked = sorted(goods, key=lambda v: (-po_count[v], v))
    out["vendor_concentration"] = {
        "goods_vendors": len(goods), "vendors_with_pos": sum(1 for v in goods if po_count[v]),
        "top_20pct_share_of_pos": _pct(sum(po_count[v] for v in ranked[:top]), len(pos)),
        "top_20pct_share_of_po_spend": _pct(int(sum(sorted(spend.values(), reverse=True)[:top])),
                                            int(sum(spend.values()))),
    }
    sku_cat = {s["sku_id"]: s["category"] for s in t["sku"]}
    by_cat = defaultdict(list)
    for l in lines:
        by_cat[sku_cat[l["sku_id"]]].append(D(l["line_net_amount"]))
    out["po_line_net_by_category"] = {c: {"n": len(v), "p10": _q(v, 10), "median": _q(v, 50), "p90": _q(v, 90),
                                          "max": _q(v, 100)} for c, v in sorted(by_cat.items())}
    out["po_lines_per_po"] = dict(sorted(Counter(int(p["line_count"]) for p in pos).items()))

    def weekday_share(days):
        return _pct(sum(1 for d in days if date.fromisoformat(d[:10]).weekday() < 5), len(days))
    out["weekday_share"] = {"po_date": weekday_share([p["po_date"] for p in pos]),
                            "grn_received": weekday_share([g["received_date"] for g in t["goods_receipt"]]),
                            "invoice_date": weekday_share([i["invoice_date"] for i in t["invoice"]]),
                            "received_at": weekday_share([m["received_at"] for m in t["intake_manifest"]])}
    po_date = {p["po_id"]: date.fromisoformat(p["po_date"]) for p in pos}
    po_cat = {}
    for l in lines:
        po_cat.setdefault(l["po_id"], sku_cat[l["sku_id"]])
    lead = defaultdict(list)
    first_grn = {}
    for g in sorted(t["goods_receipt"], key=lambda g: g["grn_id"]):
        first_grn.setdefault(g["po_id"], date.fromisoformat(g["received_date"]))
    for po_id, d in first_grn.items():
        lead[po_cat[po_id]].append(D((d - po_date[po_id]).days))
    out["lead_time_days_by_category"] = {c: {"median": _q(v, 50), "p90": _q(v, 90)} for c, v in sorted(lead.items())}
    out["payment_terms_mix"] = dict(sorted(Counter(v["payment_terms_code"] for v in t["vendor"]).items()))
    out["channel_mix_documents"] = dict(sorted(Counter(m["channel"] for m in t["intake_manifest"]).items()))
    out["email_from_forwarding_mailbox"] = sum(1 for m in t["intake_manifest"] if m["channel"] == "EMAIL"
                                              and not m["sender_address"].startswith("ap@vnd-"))
    out["invoices_received_by_month"] = dict(sorted(Counter(m["received_at"][:7] for m in t["intake_manifest"]).items()))
    gross = [D(i["header_gross_amount"]) for i in t["invoice"]]
    out["invoice_gross"] = {"p10": _q(gross, 10), "median": _q(gross, 50), "p90": _q(gross, 90), "max": _q(gross, 100)}
    if gt:
        out["approval_bands"] = dict(sorted(Counter(r["expected_approval_band"] or "not eligible" for r in gt).items()))
        out["final_status_at_as_of"] = dict(sorted(Counter(r["expected_final_status"] for r in gt).items()))
        seq = {m["doc_id"]: int(m["intake_seq"]) for m in t["intake_manifest"]}
        n = len(gt)
        deciles = defaultdict(lambda: [0] * 10)
        for r in gt:
            if r["scenario_category"] != "CLEAN":
                deciles[r["scenario_category"]][min(9, (seq[r["doc_id"]] - 1) * 10 // n)] += 1
        out["scenario_spread_by_intake_decile"] = dict(sorted(deciles.items()))
    return out


def to_markdown(s: dict, title: str) -> str:
    out = [f"# {title}", ""]
    for key, value in s.items():
        out.append(f"## {key.replace('_', ' ')}")
        out.append("")
        if isinstance(value, dict) and value and all(isinstance(v, dict) for v in value.values()):
            cols = list(next(iter(value.values())))
            out += ["| key | " + " | ".join(cols) + " |", "|---|" + "---|" * len(cols)]
            out += [f"| {k} | " + " | ".join(str(v[c]) for c in cols) + " |" for k, v in value.items()]
        elif isinstance(value, dict):
            out += ["| key | value |", "|---|---|"] + [f"| {k} | {v} |" for k, v in value.items()]
        else:
            out.append(str(value))
        out.append("")
    return "\n".join(out)
