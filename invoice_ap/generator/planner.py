"""Scenario planner: turns the exact allocation into concrete POs, deliveries and invoices.

Every random draw happens here, once. materialize() then builds the baseline phase (no injected
anomalies) and the final phase (injections applied) from the same plan, so the two differ only
by the labelled injections.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal

from ..common import ids
from ..common.enums import UOM_DECIMALS
from ..common.money import money
from . import params as P
from .allocation import ARCHETYPES
from .catalogue import SUBSCENARIOS
from .rng import between, shuffled, stream, uniform_decimal, weighted_choice
from .world import TAX_CODES, StatusEvent, User, Vendor, World, ts

LINE_CODES = {"C-PRICE-AT-TOL", "C-PRICE-INSIDE", "PV-BOUNDARY-OUT", "C-QTY-AT-TOL", "QM-BOUNDARY-OUT",
              "C-OVERRECEIPT-WITHIN", "QM-OVERBILL-RECEIVED", "QM-CUMULATIVE", "QM-EXCEEDS-PO-OVERRECEIPT",
              "QM-EXCEEDS-PO-AND-RECEIVED", "C-TAX-ROUNDING", "TV-TAX-AMOUNT"}
PRICE_HALF = {"C-PRICE-AT-TOL", "C-PRICE-INSIDE", "PV-BOUNDARY-OUT"}
QTY_BOUNDARY = {"C-QTY-AT-TOL", "QM-BOUNDARY-OUT"}
QTY_TWENTY = {"QM-OVERBILL-RECEIVED", "QM-CUMULATIVE", "QM-EXCEEDS-PO-OVERRECEIPT", "QM-EXCEEDS-PO-AND-RECEIVED"}
TAXED = {"C-TAX-ROUNDING", "TV-TAX-AMOUNT"}
PARTIAL_A11 = {"C-PARTIAL-OPEN", "QM-PARTIAL-BILLED-FULL"}
DEDICATED = ("TV-CLOSED", "TV-BLOCKED")


def quantum(uom: str) -> Decimal:
    return Decimal(1).scaleb(-UOM_DECIMALS[uom])


def floor_q(x: Decimal, uom: str) -> Decimal:
    return x.quantize(quantum(uom), rounding=ROUND_FLOOR)


def ceil_q(x: Decimal, uom: str) -> Decimal:
    return x.quantize(quantum(uom), rounding=ROUND_CEILING)


def part_of(q: Decimal, pct: int, uom: str) -> Decimal:
    """A partial quantity: floor(q x pct%), kept inside [one quantum, q - one quantum]."""
    step = quantum(uom)
    return min(max(floor_q(q * pct / 100, uom), step), q - step)


@dataclass
class POLine:
    number: int
    sku: object
    qty: Decimal
    price: Decimal
    tax_code: str
    line_id: str = ""

    @property
    def uom(self) -> str:
        return self.sku.uom


@dataclass
class Delivery:
    day: date
    minute: int
    qty: dict[int, Decimal]                  # line number -> received quantity (baseline)
    final_qty: dict[int, Decimal] = field(default_factory=dict)  # injected over-receipt (final only)
    grn_id: str = ""


@dataclass
class PO:
    key: int
    archetype: str
    codes: list[str] = field(default_factory=list)
    lines_n: int = 1
    pair: int | None = None
    vendor: Vendor | None = None
    requester: User | None = None
    po_date: date | None = None
    minute: int = 0
    lead: int = 0
    lines: list[POLine] = field(default_factory=list)
    deliveries: list[Delivery] = field(default_factory=list)
    po_id: str = ""


@dataclass
class ServiceLine:
    description: str
    uom: str
    qty: Decimal
    price: Decimal
    tax_code: str


@dataclass
class Bill:
    """One original invoice document as planned (PO-backed or non-PO)."""
    key: str
    code: str
    vendor: Vendor
    invoice_date: date
    received_date: date
    minute: int
    channel: str
    po: PO | None = None
    billed: tuple[int, ...] = ()             # delivery indices this invoice bills
    share: tuple[str, int] | None = None     # A12 partial billing: ("first"|"second", pct)
    attention: User | None = None
    services: list[ServiceLine] = field(default_factory=list)
    params: dict = field(default_factory=dict)
    final_vendor: Vendor | None = None       # TV-VENDOR-PO: the vendor that actually sends it
    final_invoice_date: date | None = None   # DATE-INVOICE-BEFORE-PO
    forward_mailbox: bool = False


@dataclass
class Dup:
    key: str
    code: str
    original: Bill
    received_date: date
    minute: int
    channel: str
    params: dict = field(default_factory=dict)


@dataclass
class Plan:
    world: World
    pos: list[PO]
    bills: list[Bill]
    dups: list[Dup]
    final_events: dict[str, list[StatusEvent]]  # vendor_id -> injected status events (final only)


# ------------------------------------------------------------------ helpers
def _day(rng, cal, start: date, end: date, weighted: bool = True) -> date:
    days = cal.business_days(start, end)
    if not days:
        raise ValueError(f"no business day in {start}..{end}")
    if not weighted:
        return days[rng.randrange(len(days))]
    return weighted_choice(rng, days, [P.MONTH_WEIGHTS.get(d.month, 8) for d in days])


def _roll(cal, d: date) -> date:
    return cal.next_business_day(d, include_today=True)


def _codes_by_placement(alloc, placement: str) -> list[str]:
    return [s.code for s in SUBSCENARIOS if s.placement == placement for _ in range(alloc.subscenarios[s.code])]


# ------------------------------------------------------------------ PO structure
def _assign_codes(pos: list[PO], alloc) -> None:
    by_arch = {a: [p for p in pos if p.archetype == a] for a in ARCHETYPES}
    a11, i = by_arch["A11"], 0
    for k in range(alloc.subscenarios["C-TN-SAME-DAY"] // 2):
        for _ in range(2):
            a11[i].codes, a11[i].pair, i = ["C-TN-SAME-DAY"], k, i + 1
    for code in _codes_by_placement(alloc, "S11"):
        a11[i].codes, i = [code], i + 1
    assert i == len(a11), "A11 slots do not match the allocation"
    second = _codes_by_placement(alloc, "S22_2")
    for j, p in enumerate(by_arch["A22"]):
        p.codes = ["C-SPLIT-PARTIAL", second[j] if j < len(second) else "C-SPLIT-FINAL"]
    fixed = {"A33": ["C-SPLIT-PARTIAL", "C-SPLIT-PARTIAL", "C-SPLIT-FINAL"], "A21": ["C-CONSOLIDATED"],
             "A12": ["C-PARTIAL-BILLING", "C-PARTIAL-BILLING"], "A01": ["MR-NO-GRN"], "A10": [], "A00": []}
    for arch, codes in fixed.items():
        for p in by_arch[arch]:
            p.codes = list(codes)


def _assign_line_counts(pos: list[PO], alloc, rng) -> None:
    counts = shuffled(rng, [k for k, n in alloc.line_histogram.items() for _ in range(n)])
    for p, c in zip(pos, counts):
        p.lines_n = c
    for p in pos:  # a true-negative pair is a repeat order: both POs carry one identical line
        if p.pair is not None and p.lines_n != 1:
            q = next(q for q in pos if q.pair is None and q.lines_n == 1)
            p.lines_n, q.lines_n = 1, p.lines_n


def _assign_vendors(pos: list[PO], world: World, rng) -> None:
    sku_n = {}
    for s in world.skus:
        sku_n[s.category] = sku_n.get(s.category, 0) + 1
    goods = [v for v in world.vendors if v.segment == "GOODS" and not v.reserved]
    for code in DEDICATED:  # these vendors get exactly one PO each, their scenario PO
        for p in [p for p in pos if code in p.codes]:
            cands = [v for v in goods if v.tier == "TAIL" and not v.reserved and sku_n[v.category] >= p.lines_n]
            p.vendor = cands[rng.randrange(len(cands))]
            p.vendor.reserved = code
    pool = [v for v in goods if not v.reserved]
    partner: dict[int, Vendor] = {}
    for p in pos:
        if p.vendor:
            continue
        if p.pair is not None and p.pair in partner:
            p.vendor = partner[p.pair]
            continue
        cands = [v for v in pool if sku_n[v.category] >= p.lines_n
                 and ("CAP-DEGRADED-SCAN" not in p.codes or v.channel == "SCAN")]
        p.vendor = weighted_choice(rng, cands, [v.weight for v in cands])
        if p.pair is not None:
            partner[p.pair] = p.vendor
    for p in pos:
        cc = P.CATEGORY_COST_CENTERS[p.vendor.category]
        cost_center = cc[rng.randrange(len(cc))]
        reqs = world.requesters(cost_center)
        p.requester = reqs[rng.randrange(len(reqs))]


def _draw_qty(rng, sku, minimum: int) -> Decimal:
    lo, hi = P.CATEGORY_PARAMS[sku.category][3]
    lo = max(lo, minimum)
    hi = max(hi, lo)
    if UOM_DECIMALS[sku.uom]:
        return (Decimal(between(rng, lo * 100, hi * 100)) / 100).quantize(quantum(sku.uom))
    return Decimal(between(rng, lo, hi))


def _build_lines(pos: list[PO], world: World, rng) -> None:
    templates: dict[int, list[POLine]] = {}
    for p in pos:
        if p.pair is not None and p.pair in templates:   # repeat order: identical line
            p.lines = [POLine(l.number, l.sku, l.qty, l.price, l.tax_code) for l in templates[p.pair]]
            continue
        skus = shuffled(rng, world.skus_in(p.vendor.category))[:p.lines_n]
        split = p.archetype in ("A22", "A33", "A21", "A12") or set(p.codes) & PARTIAL_A11
        target = next((c for c in p.codes if c in LINE_CODES), None)
        for n, sku in enumerate(skus, start=1):
            qty = _draw_qty(rng, sku, 3 if split else 1)
            price = max(money(sku.reference_price * uniform_decimal(rng, *P.PO_PRICE_JITTER)), Decimal("0.50"))
            tax = sku.tax_code
            if n == 1 and target:
                if target in PRICE_HALF:   # 2% of a multiple of 0.50 is a whole cent (exact boundary)
                    price = max(money((price * 2).quantize(Decimal(1)) / 2), Decimal("0.50"))
                if target in QTY_BOUNDARY:
                    qty = Decimal(P.BOUNDARY_QTY_MULTIPLES[rng.randrange(len(P.BOUNDARY_QTY_MULTIPLES))])
                if target == "C-OVERRECEIPT-WITHIN":
                    qty = Decimal(P.BOUNDARY_QTY_MULTIPLES[1 + rng.randrange(len(P.BOUNDARY_QTY_MULTIPLES) - 1)])
                if target in QTY_TWENTY:
                    qty = max(qty, Decimal(20))
                if target in TAXED and TAX_CODES[tax][0] == 0:
                    tax = "GST18"
                qty = qty.quantize(quantum(sku.uom))
            p.lines.append(POLine(n, sku, qty, price, tax))
        if p.pair is not None:
            templates[p.pair] = p.lines


# ------------------------------------------------------------------ timeline and deliveries
def _delivery_quantities(p: PO, rng) -> list[dict[int, Decimal]]:
    codes, arch = set(p.codes), p.archetype
    if arch == "A11":
        if codes & PARTIAL_A11:
            q = {l.number: part_of(l.qty, between(rng, *P.PARTIAL_PCT), l.uom) for l in p.lines}
        else:
            q = {l.number: l.qty for l in p.lines}
        l1 = p.lines[0]
        if "C-OVERRECEIPT-WITHIN" in codes:
            extra = max(floor_q(l1.qty * uniform_decimal(rng, *P.OVER_RECEIPT_WITHIN), l1.uom), quantum(l1.uom))
            q[1] = l1.qty + extra
            assert q[1] < l1.qty * Decimal("1.05")
        if "C-QTY-AT-TOL" in codes:
            q[1] = (l1.qty * Decimal("1.05")).quantize(quantum(l1.uom))
            assert q[1] == l1.qty * Decimal("1.05")
        return [q]
    if arch in ("A22", "A21"):
        first = {l.number: part_of(l.qty, between(rng, *P.PARTIAL_PCT), l.uom) for l in p.lines}
        return [first, {l.number: l.qty - first[l.number] for l in p.lines}]
    if arch == "A33":
        a = {l.number: min(part_of(l.qty, between(rng, *P.THREE_WAY_PARTIAL_PCT), l.uom),
                           l.qty - 2 * quantum(l.uom)) for l in p.lines}
        b = {l.number: part_of(l.qty - a[l.number], 50, l.uom) for l in p.lines}
        return [a, b, {l.number: l.qty - a[l.number] - b[l.number] for l in p.lines}]
    if arch in ("A12", "A10"):
        return [{l.number: l.qty for l in p.lines}]
    return []


def _receive(cal, rng, invoice_day: date, channel: str, after: date | None) -> date:
    rd = _roll(cal, invoice_day + timedelta(days=between(rng, *P.CHANNEL_DELAY_DAYS[channel])))
    if after is not None and rd <= after:
        rd = cal.next_business_day(after)
    return rd


def _slots(p: PO, rng) -> list[tuple[str, tuple[int, ...], tuple[str, int] | None]]:
    if p.archetype == "A01":
        return [(p.codes[0], (), None)]
    if p.archetype == "A21":
        return [(p.codes[0], (0, 1), None)]
    if p.archetype == "A12":
        pct = between(rng, *P.PARTIAL_PCT)
        return [(p.codes[0], (0,), ("first", pct)), (p.codes[1], (0,), ("second", pct))]
    return [(code, (k,), None) for k, code in enumerate(p.codes)]


def _timeline(p: PO, world: World, rng, start: date, latest: date) -> list[tuple]:
    """Draw the PO date, deliveries and invoice dates; return the bill specs (not yet keyed)."""
    cal = world.cal
    p.po_date = _day(rng, cal, start, latest)
    day, days = _roll(cal, p.po_date + timedelta(days=p.lead)), []
    for k in range(ARCHETYPES[p.archetype][0]):
        if k:
            day = _roll(cal, day + timedelta(days=between(rng, *P.SPLIT_SPACING_DAYS)))
        days.append(day)
    p.deliveries = [Delivery(d, between(rng, 600, 1020), q) for d, q in zip(days, _delivery_quantities(p, rng))]
    specs, previous = [], None
    for code, billed, share in _slots(p, rng):
        base = p.deliveries[billed[-1]].day if billed else _roll(cal, p.po_date + timedelta(days=p.lead))
        if code in DEDICATED:      # leaves room for a status change strictly between receipt and invoice
            inv = cal.add_business_days(base, between(rng, 3, 10))
        elif share and share[0] == "second":
            inv = cal.add_business_days(previous[3], between(rng, 5, 15))
        else:
            inv = max(_roll(cal, base + timedelta(days=between(rng, *P.INVOICE_OFFSET_DAYS))), _roll(cal, p.po_date))
        received = _receive(cal, rng, inv, p.vendor.channel, base if billed else None)
        if previous is not None and received <= previous[4]:
            received = cal.next_business_day(previous[4])           # bills of one PO arrive in order
        previous = (code, billed, share, inv, received, between(rng, 540, 1079))
        specs.append(previous)
    return specs


def _schedule_and_bill(pos: list[PO], world: World, rng) -> list[Bill]:
    cal, bills, first_of_pair = world.cal, [], {}
    for p in pos:
        lo, hi = P.CATEGORY_PARAMS[p.vendor.category][4]
        p.lead, p.minute = between(rng, lo, hi), between(rng, 540, 720)
        n_del = ARCHETYPES[p.archetype][0]
        if p.archetype == "A00":
            p.po_date = _day(rng, cal, P.LATE_PO_START, P.INTAKE_CLOSE)
            continue
        if p.archetype == "A10":
            g = _day(rng, cal, P.LATE_GRN_START, P.INTAKE_CLOSE)
            p.po_date = max(P.WINDOW_START, cal.previous_business_day(g - timedelta(days=p.lead), True))
            full = rng.randrange(10) < 7
            qty = {l.number: l.qty if full else part_of(l.qty, between(rng, *P.PARTIAL_PCT), l.uom) for l in p.lines}
            p.deliveries = [Delivery(g, between(rng, 600, 1020), qty)]
            continue
        start = date(2026, 2, 2) if "DATE-INVOICE-BEFORE-PO" in p.codes else P.WINDOW_START
        spread = p.lead + max(n_del - 1, 0) * P.SPLIT_SPACING_DAYS[0]
        worst = p.lead + max(n_del - 1, 0) * P.SPLIT_SPACING_DAYS[1] + 27 \
            + (21 if p.archetype == "A12" else 0) + (14 if set(p.codes) & set(DEDICATED) else 0)
        if p.pair is not None:      # repeat orders: second PO follows the first; common invoice date later
            if p.pair in first_of_pair:
                first = first_of_pair[p.pair]
                p.lead = first.lead
                window = (cal.add_business_days(first.po_date, 0), cal.add_business_days(first.po_date, 5))
            else:
                window = (start, P.INTAKE_CLOSE - timedelta(days=worst + 7))
                first_of_pair[p.pair] = p
            specs = _timeline(p, world, rng, *window)
        else:
            for attempt in range(12):   # optimistic window first; fall back to the worst case
                end = P.INTAKE_CLOSE - timedelta(days=(spread + 3) if attempt < 11 else worst)
                specs = _timeline(p, world, rng, start, end)
                if max(s[4] for s in specs) <= P.INTAKE_CLOSE:
                    break
        for code, billed, share, inv, received, minute in specs:
            bills.append(Bill(f"B{len(bills) + 1:05d}", code, p.vendor, inv, received, minute,
                              p.vendor.channel, p, billed, share))
    pairs: dict[int, list[Bill]] = {}
    for b in bills:
        if b.po.pair is not None:
            pairs.setdefault(b.po.pair, []).append(b)
    for pair in pairs.values():    # same vendor, same date, same amount, different POs
        common = cal.add_business_days(max(b.po.deliveries[0].day for b in pair), between(rng, 1, 5))
        for b in pair:
            b.invoice_date = common
            b.received_date = _receive(cal, rng, common, b.channel, b.po.deliveries[0].day)
    return bills


def _service_line(rng, category: str, single: bool = False) -> ServiceLine:
    uom, prices, qtys, taxes, _, descs = P.SERVICE_PARAMS[category]
    price = money(Decimal(between(rng, prices[0] // 100, prices[1] // 100) * 100))
    qty = Decimal(1) if single else Decimal(between(rng, *qtys)).quantize(quantum(uom))
    tax = weighted_choice(rng, list(taxes), list(taxes.values()))
    return ServiceLine(descs[rng.randrange(len(descs))], uom, qty, price, tax)


def _non_po_bills(world: World, rng, start_index: int) -> list[Bill]:
    alloc, cal = world.alloc, world.cal
    svc = [v for v in world.vendors if v.segment == "SERVICES" and not v.reserved]
    monthly = [v for v in svc if P.SERVICE_PARAMS[v.category][0] == "MONTH"] or svc
    total = alloc.subscenarios["C-NPO-RECURRING"]
    n_series = max(1, -(-total // 10))
    lengths = [total // n_series + (1 if i < total % n_series else 0) for i in range(n_series)]
    series_vendors = shuffled(rng, monthly)[:n_series]
    bills: list[Bill] = []

    def add(code, vendor, inv, services):
        cc = P.SERVICE_PARAMS[vendor.category][4]
        reqs = world.requesters(cc)
        b = Bill(f"B{start_index + len(bills) + 1:05d}", code, vendor, inv,
                 _receive(cal, rng, inv, vendor.channel, None), between(rng, 540, 1079), vendor.channel,
                 attention=reqs[rng.randrange(len(reqs))], services=services)
        bills.append(b)
        return b

    for vendor, length in zip(series_vendors, lengths):
        line, dom = _service_line(rng, vendor.category, single=True), between(rng, 1, 5)
        first_month = between(rng, 1, 10 - length + 1)
        for m in range(first_month, first_month + length):
            add("C-NPO-RECURRING", vendor, _roll(cal, date(2026, m, dom)),
                [ServiceLine(line.description, line.uom, line.qty, line.price, line.tax_code)])
    others = [v for v in svc if v not in series_vendors] or svc
    used: set[tuple[str, date]] = set()
    for code in ("C-NPO-ONEOFF", "TV-NPO-TAX-AMOUNT"):
        for _ in range(alloc.subscenarios[code]):
            vendor = others[rng.randrange(len(others))]
            inv = _day(rng, cal, date(2026, 1, 12), date(2026, 10, 9), weighted=False)
            while (vendor.vendor_id, inv) in used:   # one one-off per vendor per day: no DUP-03 look-alikes
                inv = cal.next_business_day(inv)
            used.add((vendor.vendor_id, inv))
            add(code, vendor, inv, [_service_line(rng, vendor.category) for _ in range(between(rng, 1, 3))])
    return bills


# ------------------------------------------------------------------ scenario parameters
def _draw_params(bills: list[Bill], world: World, rng) -> None:
    cal = world.cal
    goods = [v for v in world.vendors if v.segment == "GOODS" and not v.reserved]
    for b in bills:
        c, l1 = b.code, (b.po.lines[0] if b.po else None)
        if c in ("PV-OVER", "PV-UNDER", "PV-SPLIT-LATER"):
            b.params["factor"] = uniform_decimal(rng, *{"PV-OVER": P.PV_OVER, "PV-UNDER": P.PV_UNDER,
                                                        "PV-SPLIT-LATER": P.PV_SPLIT}[c])
        elif c == "C-PRICE-SMALL-VAR":
            f = Decimal(0)
            while f == 0:
                f = uniform_decimal(rng, *P.PRICE_SMALL_VAR)
            b.params["factor"] = f
        elif c in ("QM-OVERBILL-RECEIVED", "QM-CUMULATIVE"):
            room = floor_q(l1.qty * Decimal("0.05"), l1.uom)
            steps = int(room / quantum(l1.uom))
            b.params["extra"] = quantum(l1.uom) * between(rng, 1, max(1, steps))
        elif c == "QM-EXCEEDS-PO-AND-RECEIVED":
            b.params["extra"] = ceil_q(l1.qty * uniform_decimal(rng, *P.OVERBILL_BEYOND_PO), l1.uom)
        elif c == "QM-EXCEEDS-PO-OVERRECEIPT":
            over = l1.qty + ceil_q(l1.qty * uniform_decimal(rng, *P.OVER_RECEIPT_BEYOND), l1.uom)
            assert over > l1.qty * Decimal("1.05")
            b.po.deliveries[0].final_qty = {1: over}
        elif c == "QM-BOUNDARY-OUT":
            b.po.deliveries[0].final_qty = {1: (l1.qty * Decimal("1.05")).quantize(quantum(l1.uom)) + quantum(l1.uom)}
        elif c == "C-TAX-ROUNDING":
            b.params["cents"] = Decimal("0.01") if rng.randrange(2) else Decimal("-0.01")
        elif c in ("TV-TAX-AMOUNT", "TV-NPO-TAX-AMOUNT"):
            b.params["pct"] = between(rng, 1, 5)
            b.params["sign"] = 1 if rng.randrange(2) else -1
        elif c == "TV-TAX-CODE":
            alts = [t for t in ("GST0", "GST5", "GST18", "EXEMPT") if t != l1.tax_code]
            b.params["tax_code"] = alts[rng.randrange(len(alts))]
        elif c == "ARITH-HEADER-TOTAL":
            b.params["mode"] = "omit_line" if len(b.po.lines) > 1 and rng.randrange(2) else "transpose"
        elif c == "ARITH-LINE-EXTENSION":
            b.params["factor"] = Decimal(between(rng, 2, 10) * (1 if rng.randrange(2) else -1)) / 100
        elif c == "DATE-INVOICE-BEFORE-PO":
            d = cal.previous_business_day(b.po.po_date - timedelta(days=between(rng, 1, 20)), True)
            b.final_invoice_date = max(d, cal.next_business_day(date(2026, 1, 12), True))
            assert b.final_invoice_date < b.po.po_date
        elif c == "TV-VENDOR-PO":
            same = [v for v in goods if v.category == b.vendor.category and v is not b.vendor]
            pool = same or [v for v in goods if v is not b.vendor]
            b.final_vendor = pool[rng.randrange(len(pool))]
        elif c == "CAP-DEGRADED-SCAN":
            fields = ("header_gross_amount", "invoice_date", "vendor_invoice_number")
            b.params["unreadable_field"] = fields[rng.randrange(len(fields))]
        if b.channel == "EMAIL":
            b.forward_mailbox = rng.randrange(100) < P.EMAIL_FORWARD_PCT


def _vendor_events(bills: list[Bill], world: World, rng) -> dict[str, list[StatusEvent]]:
    """Injected (final-phase) status changes, strictly between the receipt and the invoice date."""
    cal, out = world.cal, {}
    for b in bills:
        if b.code not in DEDICATED:
            continue
        receipt = b.po.deliveries[0].day
        gap = len(cal.business_days(receipt + timedelta(days=1), b.invoice_date - timedelta(days=1)))
        change = cal.add_business_days(receipt, between(rng, 1, gap))
        assert receipt < change < b.invoice_date
        if b.code == "TV-CLOSED":
            ev = [StatusEvent("ACTIVE", "CLOSED", change, ts(change, 570), "RELATIONSHIP_ENDED")]
        else:
            ev = [StatusEvent("ACTIVE", "BLOCKED", change, ts(change, 570), "KYC_DOCUMENTS_EXPIRED")]
            back = cal.add_business_days(b.received_date, between(rng, 5, 15))
            if back <= world.as_of:
                ev.append(StatusEvent("BLOCKED", "ACTIVE", back, ts(back, 575), "KYC_RENEWED"))
        out[b.vendor.vendor_id] = ev
    return out


# ------------------------------------------------------------------ duplicates
def _duplicates(bills: list[Bill], world: World, rng) -> list[Dup]:
    cal, alloc, used, dups = world.cal, world.alloc, set(), []
    cutoff = date(2026, 9, 30)
    eligible = [b for b in bills if b.po and b.code != "CAP-DEGRADED-SCAN" and b.received_date <= cutoff]
    plain = [b for b in eligible if b.po.pair is None and b.code not in ("C-PARTIAL-BILLING", "TV-VENDOR-PO")]
    recurring = [b for b in bills if b.code == "C-NPO-RECURRING" and b.received_date <= cutoff]
    pools = {"DUP-EXACT": eligible, "DUP-EXACT-NORMALIZED": plain, "DUP-EXACT-NPO": recurring,
             "DUP-NUMBER-REUSE": plain, "DUP-CONTENT": plain}
    for s in [s for s in SUBSCENARIOS if s.placement == "DUP"]:
        pool = [b for b in shuffled(rng, pools[s.code]) if b.key not in used]
        for original in pool[:alloc.subscenarios[s.code]]:
            used.add(original.key)
            params: dict = {}
            channel = original.channel
            if s.code in ("DUP-EXACT", "DUP-EXACT-NORMALIZED") and rng.randrange(2):
                channel = "EMAIL" if channel in ("PORTAL", "EDI") else "PORTAL"
            start = original.received_date
            if s.code == "DUP-NUMBER-REUSE":
                params["rebill_date"] = cal.add_business_days(original.invoice_date, between(rng, 1, 5))
                params["price_factor"] = Decimal(between(rng, 3, 8)) / 100
                start = max(start, params["rebill_date"])
            if s.code == "DUP-CONTENT":
                params["suffix"] = ("-R", "A", "-RV")[rng.randrange(3)]  # letters: cannot collide with a genuine number
            received = cal.add_business_days(start, between(rng, 1, 10))
            assert received <= P.INTAKE_CLOSE
            dups.append(Dup(f"D{len(dups) + 1:05d}", s.code, original, received, between(rng, 540, 1079),
                            channel, params))
        assert len([d for d in dups if d.code == s.code]) == alloc.subscenarios[s.code], s.code
    return dups


# ------------------------------------------------------------------ IDs and plan
def _assign_ids(pos: list[PO]) -> None:
    for n, p in enumerate(sorted(pos, key=lambda p: (p.po_date, p.key)), start=1):
        p.po_id = ids.po_id(n)
        for line in p.lines:
            line.line_id = ids.po_line_id(p.po_id, line.number)
    deliveries = sorted(((d.day, d.minute, p.po_id, k, d) for p in pos for k, d in enumerate(p.deliveries)),
                        key=lambda t: t[:4])
    for n, (*_, d) in enumerate(deliveries, start=1):
        d.grn_id = ids.grn_id(n)


def make_plan(world: World) -> Plan:
    alloc, seed = world.alloc, world.seed
    rng = stream(seed, "structure")
    pos = shuffled(rng, [PO(0, a) for a, n in alloc.archetypes.items() for _ in range(n)])
    for k, p in enumerate(pos):
        p.key = k
    _assign_codes(pos, alloc)
    _assign_line_counts(pos, alloc, rng)
    _assign_vendors(pos, world, stream(seed, "po_vendors"))
    _build_lines(pos, world, stream(seed, "po_lines"))
    bills = _schedule_and_bill(pos, world, stream(seed, "timeline"))
    bills += _non_po_bills(world, stream(seed, "non_po"), len(bills))
    _draw_params(bills, world, stream(seed, "injections"))
    events = _vendor_events(bills, world, stream(seed, "vendor_events"))
    dups = _duplicates(bills, world, stream(seed, "duplicates"))
    _assign_ids(pos)
    late = [b.key for b in bills if b.received_date > P.INTAKE_CLOSE]
    assert not late, f"invoices received after intake close: {late[:5]}"
    return Plan(world, pos, bills, dups, events)
