"""Reference data, users, SKUs and vendors (generation steps 1-2)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from fractions import Fraction

from ..common import ids
from ..common.calendar import BusinessCalendar
from ..common.enums import COST_CENTERS, GOODS_CATEGORIES, SERVICE_CATEGORIES
from ..common.money import money
from . import params as P
from .allocation import Allocation, apportion, round_half_up
from .rng import between, lognormal, shuffled, stream, weighted_choice

IST = "+05:30"
TAX_CODES = {  # code: (rate %, category, valid_from, valid_to)
    "GST0": (Decimal("0.00"), "ZERO_RATED", date(2017, 7, 1), None),
    "GST5": (Decimal("5.00"), "REDUCED", date(2017, 7, 1), None),
    "GST12": (Decimal("12.00"), "STANDARD", date(2017, 7, 1), date(2025, 9, 21)),
    "GST18": (Decimal("18.00"), "STANDARD", date(2017, 7, 1), None),
    "EXEMPT": (Decimal("0.00"), "EXEMPT", date(2017, 7, 1), None),
}
TERMS_DAYS = {"NET15": 15, "NET30": 30, "NET45": 45, "NET60": 60}
ROLE_TEXT = {
    "BUSINESS_REQUESTER": ("Business requester", "Raises POs, confirms receipts, answers price/receipt/quantity queries, approves non-PO invoices"),
    "PROCESS_OWNER": ("Process owner", "Owns the AP policy; decides policy exceptions (invoice before PO, PO quantity overrun)"),
    "APPROVER": ("Approver", "Approves invoices by amount band and level (L1, L2, L3)"),
    "OPERATIONS_ANALYST": ("Operations analyst", "Works the AP queues: capture review, duplicates, validation, tax, payment watch"),
    "SYSTEM_ADMINISTRATOR": ("System administrator", "Maintains the vendor master, the policy file, runs and the audit trail"),
    "SYSTEM": ("AP automation engine", "Automated capture, matching, routing, auto-approval and scheduling"),
}


def ts(d: date, minutes: int) -> datetime:
    """Timestamp on day d at 00:00 + minutes (IST, timezone carried as text)."""
    return datetime.combine(d, time()) + timedelta(minutes=minutes)


@dataclass
class User:
    user_id: str
    display_name: str
    role_code: str
    responsibility: str
    cost_center: str | None = None
    approval_level: str | None = None

    @property
    def email(self) -> str:
        return self.display_name.lower().replace(" - ", ".").replace(" ", ".") + "@example.com"


@dataclass
class Sku:
    sku_id: str
    description: str
    category: str
    uom: str
    tax_code: str
    reference_price: Decimal
    lead: tuple[int, int]


@dataclass
class StatusEvent:
    from_status: str | None
    to_status: str
    effective: date
    recorded_at: datetime
    reason: str


@dataclass
class Vendor:
    vendor_id: str
    name: str
    trn: str
    segment: str
    category: str
    tier: str
    terms: str
    channel: str
    onboarded: date
    weight: int = 0                 # PO activity weight (Zipf-like), GOODS only
    reserved: str = ""              # TV-CLOSED / TV-BLOCKED / HISTORIC-CLOSED: no ordinary activity
    events: list[StatusEvent] = field(default_factory=list)

    @property
    def remit_email(self) -> str:
        return f"ap@{self.vendor_id.lower()}.example"


@dataclass
class World:
    seed: int
    alloc: Allocation
    cal: BusinessCalendar
    users: list[User]
    skus: list[Sku]
    vendors: list[Vendor]
    as_of: date = date(2026, 10, 22)

    def requesters(self, cost_center: str) -> list[User]:
        return [u for u in self.users if u.role_code == "BUSINESS_REQUESTER" and u.cost_center == cost_center]

    def user(self, responsibility: str, cost_center: str | None = None) -> User:
        return next(u for u in self.users if u.responsibility == responsibility
                    and (cost_center is None or u.cost_center == cost_center))

    def skus_in(self, category: str) -> list[Sku]:
        return [s for s in self.skus if s.category == category]


def _cc(cost_center: str) -> str:
    return "IT" if cost_center == "IT" else cost_center.title()


def make_users() -> list[User]:
    rows = [("AP Automation Engine", "SYSTEM", "SYSTEM_USER", None, None),
            ("Vendor Master Admin", "SYSTEM_ADMINISTRATOR", "VENDOR_MASTER_OWNER", None, None),
            ("Platform Admin", "SYSTEM_ADMINISTRATOR", "PLATFORM_ADMIN", None, None),
            ("AP Policy Owner", "PROCESS_OWNER", "POLICY_OWNER", None, None)]
    rows += [(f"AP Analyst {i:02d}", "OPERATIONS_ANALYST", "AP_ANALYST", None, None) for i in range(1, 5)]
    rows += [(f"Approver L1 - {_cc(cc)}", "APPROVER", "COST_CENTER_MANAGER", cc, "L1") for cc in COST_CENTERS]
    rows += [("Finance Controller", "APPROVER", "FINANCE_CONTROLLER", None, "L2"),
             ("Chief Financial Officer", "APPROVER", "CHIEF_FINANCIAL_OFFICER", None, "L3")]
    rows += [(f"Requester - {_cc(cc)} {i:02d}", "BUSINESS_REQUESTER", "REQUESTER", cc, None)
             for cc in COST_CENTERS for i in (1, 2)]
    return [User(ids.user_id(n), *row) for n, row in enumerate(rows, start=1)]


def _business_day(rng, cal: BusinessCalendar, start: date, end: date) -> date:
    days = cal.business_days(start, end)
    return days[rng.randrange(len(days))]


def make_skus(alloc: Allocation, seed: int) -> list[Sku]:
    rng = stream(seed, "skus")
    total = max(60, round_half_up(alloc.targets.po_lines * Fraction(2, 11)))
    per_cat = apportion(total, list(P.CATEGORY_SKU_WEIGHTS.items()), 1)
    skus, n = [], 0
    for category in GOODS_CATEGORIES:
        uom, median, sigma, _, lead, taxes = P.CATEGORY_PARAMS[category]
        nouns = P.SKU_NOUNS[category]
        for i in range(per_cat[category]):
            n += 1
            price = max(money(lognormal(rng, median, sigma)), Decimal("1.00"))
            tax = weighted_choice(rng, list(taxes), list(taxes.values()))
            desc = f"{nouns[i % len(nouns)]} - grade {chr(65 + (i // len(nouns)) % 26)} - M{n:03d}"
            skus.append(Sku(ids.sku_id(n), desc, category, uom, tax, price, lead))
    return skus


def make_vendors(alloc: Allocation, cal: BusinessCalendar, seed: int) -> list[Vendor]:
    rng = stream(seed, "vendors")
    count = alloc.targets.vendors
    segments = shuffled(rng, [s for s, k in alloc.vendor_segments.items() for _ in range(k)])
    tiers = shuffled(rng, [t for t, k in alloc.vendor_tiers.items() for _ in range(k)])
    goods_idx = [i for i in range(count) if segments[i] == "GOODS"]
    service_idx = [i for i in range(count) if segments[i] == "SERVICES"]
    category = {}
    for idx, cats, weights, floor in ((goods_idx, GOODS_CATEGORIES, P.CATEGORY_SKU_WEIGHTS, 1),
                                      (service_idx, P.SERVICE_CATEGORY_ORDER, {c: 1 for c in SERVICE_CATEGORIES}, 0)):
        counts = apportion(len(idx), [(c, weights[c]) for c in cats], floor)
        for i, c in zip(idx, shuffled(rng, [c for c in cats for _ in range(counts[c])])):
            category[i] = c
    terms = shuffled(rng, [t for t, k in apportion(count, list(P.TERMS_WEIGHTS), 1).items() for _ in range(k)])
    channel = {}
    for key, weights in P.CHANNEL_WEIGHTS.items():
        group = [i for i in range(count) if (segments[i], tiers[i]) == key]
        if group:
            counts = apportion(len(group), list(weights), 0)
            for i, ch in zip(group, shuffled(rng, [c for c, k in counts.items() for _ in range(k)])):
                channel[i] = ch
    pairs = shuffled(rng, [a + b for a in P.NAME_SYLLABLES for b in P.NAME_SYLLABLES if a != b])
    trns: list[str] = []
    while len(trns) < count:
        trn = f"TRN-{between(rng, 100_000_000, 999_999_999)}"
        if trn not in trns:
            trns.append(trn)
    vendors = []
    for i in range(count):
        early = tiers[i] == "STRATEGIC"
        onboard = _business_day(rng, cal, P.ONBOARD_START, date(2022, 12, 30) if early else P.ONBOARD_END)
        name = f"{pairs[i].capitalize()} {P.CATEGORY_NAME_NOUNS[category[i]]} {P.LEGAL_SUFFIXES[i % 5]}"
        v = Vendor(ids.vendor_id(i + 1), name, trns[i], segments[i], category[i], tiers[i], terms[i],
                   channel[i], onboard)
        v.events.append(StatusEvent(None, "ACTIVE", onboard, ts(onboard, 600 + between(rng, 0, 240)), "ONBOARDED"))
        vendors.append(v)
    # Zipf-like activity weights over GOODS vendors: rank by tier, then a seeded order within tier.
    order = {"STRATEGIC": 0, "CORE": 1, "TAIL": 2}
    goods = shuffled(rng, [v for v in vendors if v.segment == "GOODS"])
    goods.sort(key=lambda v: order[v.tier])
    for rank, v in enumerate(goods, start=1):
        v.weight = 1_000_000 // rank
    _historic_status_changes(vendors, cal, rng)
    return vendors


def _historic_status_changes(vendors: list[Vendor], cal: BusinessCalendar, rng) -> None:
    """2025 block windows and 2025 closures on vendors that have no 2026 activity in them."""
    n = len(vendors)
    eligible = [v for v in vendors if v.onboarded < date(2025, 1, 1) and v.tier == "TAIL"]
    eligible = shuffled(rng, eligible)
    closed = max(1, round_half_up(Fraction(n * P.HISTORIC_CLOSED_PCT, 100)))
    blocked = max(1, round_half_up(Fraction(n * P.HISTORIC_BLOCKED_PCT, 100)))
    for v in eligible[:closed]:
        d = _business_day(rng, cal, date(2025, 2, 3), date(2025, 11, 28))
        v.events.append(StatusEvent("ACTIVE", "CLOSED", d, ts(d, 660), "RELATIONSHIP_ENDED"))
        v.reserved = "HISTORIC-CLOSED"
    for v in eligible[closed:closed + blocked]:
        d1 = _business_day(rng, cal, date(2025, 2, 3), date(2025, 9, 30))
        d2 = cal.add_business_days(d1, between(rng, 10, 30))
        v.events.append(StatusEvent("ACTIVE", "BLOCKED", d1, ts(d1, 630), "KYC_DOCUMENTS_EXPIRED"))
        v.events.append(StatusEvent("BLOCKED", "ACTIVE", d2, ts(d2, 640), "KYC_RENEWED"))


def build_world(alloc: Allocation, policy_raw: dict, seed: int) -> World:
    cal = BusinessCalendar.from_policy(policy_raw)
    as_of = date.fromisoformat(policy_raw["policy"]["as_of_date"])
    return World(seed, alloc, cal, make_users(), make_skus(alloc, seed), make_vendors(alloc, cal, seed), as_of)
