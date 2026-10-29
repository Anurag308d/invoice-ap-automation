"""Generator parameters: every distribution and window in one reviewable place
(docs/data_generation.md section 5)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal as D

GENERATOR_VERSION = "2.0.0"
DEFAULT_SEED = 20261022

WINDOW_START = date(2026, 1, 5)     # first PO date
INTAKE_CLOSE = date(2026, 10, 21)   # last invoice receipt date (as-of 2026-10-22 is a hard limit)
LATE_PO_START = date(2026, 9, 14)   # open POs (A00) are issued from here
LATE_GRN_START = date(2026, 9, 21)  # received-not-invoiced POs (A10) are received from here
ONBOARD_START, ONBOARD_END = date(2019, 1, 1), date(2025, 12, 31)
USER_ACTIVE_FROM = date(2025, 4, 1)
MONTH_WEIGHTS = {1: 8, 2: 9, 3: 13, 4: 8, 5: 9, 6: 12, 7: 9, 8: 9, 9: 12, 10: 8}  # quarter-end peaks

# category: uom, median unit price (INR), sigma, quantity range, lead-time days, tax codes (weights)
CATEGORY_PARAMS = {
    "RAW_MATERIALS":    ("KG",   D("180"),   D("0.6"), (50, 2000), (7, 21), {"GST18": 1}),
    "ELECTRICAL":       ("EA",   D("850"),   D("0.9"), (5, 200),   (5, 15), {"GST18": 1}),
    "MRO_SPARES":       ("EA",   D("2400"),  D("1.0"), (1, 40),    (3, 30), {"GST18": 1}),
    "PACKAGING":        ("BOX",  D("95"),    D("0.5"), (50, 2000), (3, 10), {"GST18": 4, "GST5": 1}),
    "IT_HARDWARE":      ("EA",   D("18000"), D("0.8"), (1, 30),    (7, 28), {"GST18": 1}),
    "OFFICE_SUPPLIES":  ("PACK", D("320"),   D("0.7"), (5, 200),   (2, 7),  {"GST18": 3, "GST5": 1, "EXEMPT": 1}),
    "SAFETY_EQUIPMENT": ("EA",   D("650"),   D("0.6"), (10, 300),  (3, 12), {"GST5": 2, "GST18": 1}),
    "CANTEEN_SUPPLIES": ("KG",   D("120"),   D("0.4"), (20, 500),  (1, 3),  {"GST5": 3, "GST0": 1}),
}
CATEGORY_SKU_WEIGHTS = {"RAW_MATERIALS": 15, "ELECTRICAL": 15, "MRO_SPARES": 20, "PACKAGING": 10,
                        "IT_HARDWARE": 10, "OFFICE_SUPPLIES": 12, "SAFETY_EQUIPMENT": 10,
                        "CANTEEN_SUPPLIES": 8}
CATEGORY_COST_CENTERS = {
    "RAW_MATERIALS": ("MANUFACTURING",), "ELECTRICAL": ("MANUFACTURING", "OPERATIONS"),
    "MRO_SPARES": ("OPERATIONS", "MANUFACTURING"), "PACKAGING": ("LOGISTICS", "MANUFACTURING"),
    "IT_HARDWARE": ("IT",), "OFFICE_SUPPLIES": ("CORPORATE", "IT", "OPERATIONS"),
    "SAFETY_EQUIPMENT": ("OPERATIONS", "FACILITIES"), "CANTEEN_SUPPLIES": ("FACILITIES",),
}
SKU_NOUNS = {
    "RAW_MATERIALS": ("MS sheet", "Aluminium ingot", "Copper rod", "PVC resin", "HDPE granules",
                      "Stainless steel coil", "Brass rod", "Zinc ingot"),
    "ELECTRICAL": ("Copper cable", "MCB switch", "LED panel", "Contactor", "Cable tray",
                   "Junction box", "Relay module", "Terminal block"),
    "MRO_SPARES": ("Ball bearing", "V-belt", "Hydraulic seal", "Gear coupling", "Pump impeller",
                   "Valve actuator", "Pressure gauge", "Chain sprocket"),
    "PACKAGING": ("Corrugated box", "Stretch film roll", "Pallet", "Bubble wrap roll", "Carton sealer tape",
                  "Foam insert", "Strapping roll", "Shipping label roll"),
    "IT_HARDWARE": ("Laptop", "Desktop workstation", "Network switch", "Monitor", "Rack server",
                    "Wireless access point", "Storage array", "Docking station"),
    "OFFICE_SUPPLIES": ("Copier paper", "Toner cartridge", "File folder", "Whiteboard marker",
                        "Notebook", "Stapler", "Desk organiser", "Printer ribbon"),
    "SAFETY_EQUIPMENT": ("Safety helmet", "Safety shoes", "Nitrile gloves", "Ear muffs",
                         "Safety goggles", "Hi-vis vest", "Respirator mask", "Fall-arrest harness"),
    "CANTEEN_SUPPLIES": ("Basmati rice", "Toor dal", "Sunflower oil", "Wheat flour", "Sugar",
                         "Tea leaves", "Coffee powder", "Milk powder"),
}
# Non-PO services: unit of measure, unit-price range (INR), quantity range, tax codes, cost centre
SERVICE_PARAMS = {
    "FACILITY_SERVICES":     ("MONTH", (15000, 250000), (1, 1),  {"GST18": 1}, "FACILITIES",
                              ("Housekeeping services", "Security services", "Pest control services")),
    "PROFESSIONAL_SERVICES": ("HR",    (1500, 6000),    (8, 80), {"GST18": 3, "EXEMPT": 1}, "CORPORATE",
                              ("Audit advisory", "Legal consultation", "Training programme")),
    "IT_SERVICES":           ("MONTH", (5000, 150000),  (1, 1),  {"GST18": 1}, "IT",
                              ("Cloud subscription", "Software licence", "Managed network service")),
    "LOGISTICS_SERVICES":    ("JOB",   (2000, 60000),   (1, 4),  {"GST18": 2, "GST5": 1}, "LOGISTICS",
                              ("Freight charges", "Courier services", "Warehousing charges")),
}
SERVICE_CATEGORY_ORDER = ("FACILITY_SERVICES", "IT_SERVICES", "PROFESSIONAL_SERVICES", "LOGISTICS_SERVICES")

NAME_SYLLABLES = ("ar", "bel", "cor", "dav", "en", "fal", "gar", "hal", "ir", "jor", "kav", "lum",
                  "mer", "nov", "or", "par", "quin", "ros", "sel", "tav", "ur", "vel", "wyn", "zan")
CATEGORY_NAME_NOUNS = {
    "RAW_MATERIALS": "Metals", "ELECTRICAL": "Electricals", "MRO_SPARES": "Engineering Spares",
    "PACKAGING": "Packaging", "IT_HARDWARE": "Infotech", "OFFICE_SUPPLIES": "Stationers",
    "SAFETY_EQUIPMENT": "Safety Gear", "CANTEEN_SUPPLIES": "Foods",
    "FACILITY_SERVICES": "Facility Services", "PROFESSIONAL_SERVICES": "Consulting",
    "IT_SERVICES": "Cloud Services", "LOGISTICS_SERVICES": "Logistics",
}
LEGAL_SUFFIXES = ("Pvt Ltd", "LLP", "Enterprises", "Industries", "& Co")

TERMS_WEIGHTS = (("NET15", 10), ("NET30", 45), ("NET45", 30), ("NET60", 15))
CHANNEL_WEIGHTS = {  # by segment and tier (exact counts via apportionment)
    ("GOODS", "STRATEGIC"): (("EDI", 60), ("PORTAL", 40)),
    ("GOODS", "CORE"): (("PORTAL", 50), ("EMAIL", 35), ("EDI", 15)),
    ("GOODS", "TAIL"): (("EMAIL", 50), ("SCAN", 30), ("PORTAL", 20)),
    ("SERVICES", "STRATEGIC"): (("PORTAL", 60), ("EMAIL", 40)),
    ("SERVICES", "CORE"): (("EMAIL", 60), ("PORTAL", 40)),
    ("SERVICES", "TAIL"): (("EMAIL", 70), ("SCAN", 30)),
}
CHANNEL_DELAY_DAYS = {"PORTAL": (0, 1), "EDI": (0, 1), "EMAIL": (0, 3), "SCAN": (3, 8)}
EMAIL_FORWARD_PCT = 15               # share of EMAIL documents sent from a forwarding mailbox (ADR-037)
HISTORIC_BLOCKED_PCT, HISTORIC_CLOSED_PCT = 2, 1   # vendors with a 2025 block window / a 2025 closure

SPLIT_SPACING_DAYS = (5, 20)
INVOICE_OFFSET_DAYS = (-3, 7)        # invoice date relative to the delivery it bills
PARTIAL_PCT = (40, 70)               # partial first delivery or first partial bill, % of ordered
THREE_WAY_PARTIAL_PCT = (30, 40)     # each of the first two deliveries of an A33 PO
PO_PRICE_JITTER = ("0.92", "1.08")   # PO unit price = SKU reference price x U(0.92, 1.08)

# scenario parameter ranges (fractions are exact Decimals; quantities use the unit-of-measure quantum)
PV_OVER = ("0.0250", "0.1500")
PV_UNDER = ("-0.1000", "-0.0250")
PV_SPLIT = ("0.0300", "0.1200")
PRICE_SMALL_VAR = ("-0.0150", "0.0150")
OVER_RECEIPT_WITHIN = ("0.0100", "0.0400")
OVER_RECEIPT_BEYOND = ("0.0600", "0.2000")
OVERBILL_BEYOND_PO = ("0.1000", "0.3000")
BOUNDARY_QTY_MULTIPLES = (20, 40, 60, 80, 100, 120, 200)   # ordered x 5% is a whole number
