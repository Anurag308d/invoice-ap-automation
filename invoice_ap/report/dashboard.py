"""Offline HTML dashboard (R36): one self-contained file, no CDN, no external fonts, no clock.

It shows the KPIs, the validation and evaluation results, a work queue per actor, and an invoice
explorer with each invoice's decision trace (exceptions, line match, approvals, payment, events).
All data is embedded as JSON; the page renders it with a few lines of plain JavaScript.
"""
from __future__ import annotations

import json
from collections import defaultdict
from html import escape
from pathlib import Path

from ..spec.io import read_table
from .queue import ROLES, queue_items


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def _explorer(root: Path) -> list:
    """One compact record per invoice, in intake order."""
    p = root / "processed"
    cap = read_table(p, "captured_invoice")
    by = lambda table, key="invoice_id": _group(read_table(p, table), key)
    dec = {d["invoice_id"]: d for d in read_table(p, "invoice_decision")}
    exc, lines, apr, pay, ev = by("ap_exception"), by("match_result"), by("approval"), by("payment"), by("ap_event")
    out = []
    for c in cap:
        i, d = c["invoice_id"], dec[c["invoice_id"]]
        out.append([i, c["doc_id"], c["channel"], c["vendor_id"], c["vendor_invoice_number"] or "", c["invoice_date"],
                    c["po_id"], c["header_gross_amount"], d["status_as_of"], d["primary_issue"], d["match_status"],
                    d["approval_band"], d["duplicate_of_invoice_id"],
                    [[e["exception_type"], e["rule_id"], e["invoice_line_id"][-2:] if e["invoice_line_id"] else "",
                      e["expected_value"], e["actual_value"], e["assigned_role"], e["queue"], e["sla_due_date"],
                      e["status_as_of"]] for e in exc.get(i, [])],
                    [[m["invoice_line_id"][-2:], m["po_line_id"], m["price_status"], m["qty_status"], m["tax_status"],
                      m["line_match_status"]] for m in lines.get(i, [])],
                    [[a["level"], a["approver_user_id"], a["status_as_of"], (a["decided_at"] or "")[:10]]
                     for a in apr.get(i, [])],
                    [[x["payment_id"], x["payment_method"], x["due_date"], x["scheduled_date"], x["status_as_of"]]
                     for x in pay.get(i, [])],
                    ";".join(f"{e['event_at'][5:16]}|{e['entity_type'][0]}|{e['to_status']}|{e['rule_id']}"
                             for e in ev.get(i, []))])
    return out


def _group(rows: list[dict], key: str) -> dict:
    out = defaultdict(list)
    for r in rows:
        out[r[key]].append(r)
    return out


CSS = """
:root{--bg:#f7f7f5;--fg:#1d1d1b;--muted:#5f5f5a;--card:#fff;--line:#deded8;--accent:#1f5f8b;--bad:#a8322d;--ok:#2d6a3e}
@media (prefers-color-scheme:dark){:root{--bg:#161616;--fg:#ececea;--muted:#a3a39d;--card:#1f1f1f;--line:#333;
--accent:#7fb3d9;--bad:#e08079;--ok:#8fc79c}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.45 system-ui,-apple-system,
Segoe UI,Roboto,sans-serif}header,main{max-width:1200px;margin:0 auto;padding:16px}h1{font-size:22px;margin:8px 0}
h2{font-size:17px;margin:28px 0 8px}.muted{color:var(--muted)}.tiles{display:grid;grid-template-columns:
repeat(auto-fit,minmax(170px,1fr));gap:10px}.tile{background:var(--card);border:1px solid var(--line);border-radius:8px;
padding:10px 12px}.tile b{display:block;font-size:20px}.wrap{overflow-x:auto}table{border-collapse:collapse;width:100%;
background:var(--card);font-size:13px}th,td{border-bottom:1px solid var(--line);padding:5px 8px;text-align:left;
vertical-align:top}th{position:sticky;top:0;background:var(--card)}.bad{color:var(--bad);font-weight:600}
.ok{color:var(--ok);font-weight:600}.tabs button{border:1px solid var(--line);background:var(--card);color:var(--fg);
padding:6px 10px;border-radius:6px;margin:0 6px 6px 0;cursor:pointer}.tabs button.on{border-color:var(--accent);
color:var(--accent)}input{padding:7px 9px;width:min(420px,100%);border:1px solid var(--line);border-radius:6px;
background:var(--card);color:var(--fg)}.bar{height:10px;background:var(--accent);border-radius:3px}pre{white-space:pre-wrap}
"""

JS = """
const D=JSON.parse(document.getElementById('data').textContent);
const h=(t,a)=>{const e=document.createElement(t);if(a)e.textContent=a;return e};
function table(head,rows){const w=h('div');w.className='wrap';const t=h('table');const tr=h('tr');
head.forEach(x=>tr.appendChild(h('th',x)));t.appendChild(tr);rows.forEach(r=>{const row=h('tr');
r.forEach(x=>row.appendChild(h('td',x==null?'':String(x))));t.appendChild(row)});w.appendChild(t);return w}
function showQueue(role){document.querySelectorAll('#tabs button').forEach(b=>b.classList.toggle('on',b.dataset.r===role));
const q=D.queues[role];const box=document.getElementById('queue');box.innerHTML='';
box.appendChild(h('p',q.length+' open items for '+role+' ('+q.filter(i=>i.past_sla).length+
' open and past SLA at the snapshot; no resolutions simulated)'));
box.appendChild(table(['Item','Invoice','What','Queue','User','SLA due','Age (business days)','Amount'],
q.slice(0,400).map(i=>[i.id,i.invoice_id,i.what,i.queue,i.user,i.due,i.age_business_days,i.amount])));}
const roles=Object.keys(D.queues);const tabs=document.getElementById('tabs');
roles.forEach(r=>{const b=h('button',r+' ('+D.queues[r].length+')');b.dataset.r=r;b.onclick=()=>showQueue(r);tabs.appendChild(b)});
showQueue(roles[0]);
const F=['invoice','document','channel','vendor','vendor invoice no','invoice date','PO','gross','status',
'primary issue','match status','approval band','duplicate of'];
function showInvoice(q){const box=document.getElementById('inv');box.innerHTML='';q=q.trim().toUpperCase();if(!q)return;
const hits=D.invoices.filter(r=>r[0].includes(q)||r[1].includes(q)||(r[4]||'').toUpperCase().includes(q)).slice(0,1);
if(!hits.length){box.appendChild(h('p','No invoice matches.'));return}const r=hits[0];
box.appendChild(table(['Field','Value'],F.map((f,i)=>[f,r[i]])));
box.appendChild(h('h3','Exceptions'));box.appendChild(table(['Type','Rule','Line','Expected','Actual','Role','Queue',
'SLA due','Status'],r[13]));box.appendChild(h('h3','Line match'));box.appendChild(table(['Line','PO line','Price',
'Quantity','Tax','Line status'],r[14]));box.appendChild(h('h3','Approvals and payment'));
box.appendChild(table(['Level','Approver','Status','Decided'],r[15]));box.appendChild(table(['Payment','Method','Due',
'Scheduled','Status'],r[16]));const ENT={I:'INVOICE',E:'EXCEPTION',A:'APPROVAL',P:'PAYMENT'};box.appendChild(h('h3','Event log ('+r[5].slice(0,4)+
', IST)'));box.appendChild(table(['At','Entity','To','Rule'],r[17].split(';').filter(x=>x).map(x=>{const f=x.split('|');
return [f[0].replace('T',' '),ENT[f[1]],f[2],f[3]]})));}
document.getElementById('q').oninput=e=>showInvoice(e.target.value);
showInvoice(D.example);
"""


def build_dashboard(root: Path, policy) -> bytes:
    root = Path(root)
    ev = _load_json(root / "reports" / "evaluation.json") or {}
    dec = ev.get("decisions", {})
    ext = ev.get("extraction_summary", {})
    val = _load_json(root / "reports" / "validation_summary.json") or {"status": "not run", "checks": []}
    gen = _load_json(root / "reports" / "source_manifest.json") or {}
    queues = {r: queue_items(root, r, policy.as_of_date, policy.raw) for r in ROLES}
    invoices = _explorer(root)
    example = next((r[0] for r in invoices if r[9] not in ("NONE",) and r[13]), invoices[0][0])
    statuses = defaultdict(int)
    for r in invoices:
        statuses[r[8]] += 1
    k = dec.get("kpis", {})
    tiles = [("Invoices", len(invoices)), ("STP rate", k.get("stp_rate", "-")), ("Exception rate", k.get("exception_rate", "-")),
             ("Extraction silent errors", ext.get("silent_errors", "-")),
             ("Unsafe payments (R34e)", dec.get("payments", {}).get("blocked_or_unapproved_with_payment", "-")),
             ("Acceptance R34a-e", f"{dec.get('acceptance', {}).get('pass', '-')} / {len(invoices)}"),
             ("Value at risk held (INR)", dec.get("value_at_risk", {}).get("held_value_inr", "-")),
             ("Validation", f"{val['status'].upper()} ({val.get('violations', '-')} violations)")]
    total = max(1, len(invoices))
    status_rows = "".join(
        f"<tr><td>{escape(s)}</td><td>{n}</td><td style='width:60%'><div class='bar' style='width:{n * 100 // total}%'>"
        f"</div></td></tr>" for s, n in sorted(statuses.items()))
    agree = "".join(f"<tr><td>{escape(a)}</td><td>{escape(v)}</td></tr>" for a, v in dec.get("agreement", {}).items())
    per_type = "".join(
        f"<tr><td>{escape(t)}</td><td>{m['tp']}</td><td>{m['fp']}</td><td>{m['fn']}</td><td>{m['precision']}</td>"
        f"<td>{m['recall']}</td><td>{m['f1']}</td></tr>" for t, m in dec.get("per_type_invoice", {}).items())
    checks = "".join(
        f"<tr><td>{escape(c['check'])}</td><td class='{'ok' if c['status'] == 'pass' else 'bad'}'>{c['status']}</td>"
        f"<td>{c['violations']}</td><td>{c['labelled']}</td></tr>" for c in val.get("checks", []))
    backlog = dec.get("backlog", {})
    back_rows = "".join(f"<tr><td>{escape(role)}</td>" + "".join(f"<td>{n}</td>" for n in c.values()) + "</tr>"
                        for role, c in backlog.get("by_role_and_age", {}).items())
    back_head = "".join(f"<th>{escape(n)}</th>" for n in next(iter(backlog.get("by_role_and_age", {}).values()), {}))
    data = json.dumps({"queues": queues, "invoices": invoices, "example": example}, sort_keys=True,
                      separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/")
    title = f"AP automation dashboard ({gen.get('scale', root.name)})"
    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)}</title><style>{CSS}</style></head><body>
<header><h1>{escape(title)}</h1><p class="muted">Seed {gen.get('seed', '-')}, policy {escape(policy.id)}
{escape(policy.version)}, snapshot as of {policy.as_of_date}. Synthetic data; offline page, no external resources.</p></header>
<main>
<div class="tiles">{''.join(f'<div class="tile"><span class="muted">{escape(a)}</span><b>{escape(str(b))}</b></div>' for a, b in tiles)}</div>
<h2>Invoice status at the snapshot</h2><div class="wrap"><table>{status_rows}</table></div>
<h2>Work queues by actor</h2><div class="tabs" id="tabs"></div><div id="queue"></div>
<h2>Backlog: {escape(backlog.get('label', ''))}</h2>
<div class="wrap"><table><tr><th>Role</th>{back_head}</tr>{back_rows}</table></div>
<h2>Invoice explorer and decision trace</h2>
<input id="q" placeholder="Invoice ID, document ID or vendor invoice number" aria-label="Search invoices">
<div id="inv"></div>
<h2>Evaluation against ground truth</h2><div class="wrap"><table><tr><th>Item</th><th>Agreement</th></tr>{agree}</table></div>
<h2>Per exception type</h2><div class="wrap"><table><tr><th>Type</th><th>TP</th><th>FP</th><th>FN</th><th>Precision</th>
<th>Recall</th><th>F1</th></tr>{per_type}</table></div>
<h2>Validation suite</h2><div class="wrap"><table><tr><th>Check</th><th>Status</th><th>Violations</th>
<th>Labelled (expected)</th></tr>{checks}</table></div>
<p class="muted">STP: payment-ready or paid with no exception and AUTO approval. Exception rate: invoices blocked at the
snapshot. Value at risk: money held back on truly blocked invoices. Full definitions: reports/evaluation.md.</p>
</main>
<script type="application/json" id="data">{data}</script>
<script>{JS}</script>
</body></html>
"""
    return html.encode("utf-8")
