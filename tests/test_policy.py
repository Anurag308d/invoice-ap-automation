"""The versioned policy config parses exactly and is internally consistent."""
from __future__ import annotations

import copy
import tomllib

import pytest

from invoice_ap.common import enums
from invoice_ap.common.paths import DEFAULT_POLICY
from invoice_ap.common.policy import PolicyError, load_policy, validate_policy


@pytest.fixture(scope="module")
def raw():
    return tomllib.loads(DEFAULT_POLICY.read_text(encoding="utf-8"))


def test_policy_loads_and_is_versioned():
    pol = load_policy()
    assert pol.id == "AP-POLICY" and pol.version == "1.0.0"
    assert str(pol.as_of_date) == "2026-10-22"  # S1-R1-04: fixed past snapshot (<= 2026-10-28)
    assert len(pol.sha256) == 64
    assert validate_policy(pol.raw) == []


def test_precedence_and_routing_cover_every_exception_type(raw):
    assert raw["precedence"]["order"] == list(enums.EXCEPTION_TYPES)
    assert sorted(raw["routing"]["types"]) == sorted(enums.EXCEPTION_TYPES)
    blocking = {k for k, v in raw["routing"]["types"].items() if v["blocking"]}
    assert blocking == set(enums.EXCEPTION_TYPES) - set(enums.NON_BLOCKING_EXCEPTION_TYPES)


def test_vendor_identity_rules(raw):
    """S1-R1-01: VEN-04 cross-checks the authenticated sender; ID-01 assigns the ID after VEN-01."""
    assert raw["vendor"]["rule_ids"]["sender"] == "VEN-04"
    assert raw["vendor"]["sender_check_channels"] == ["PORTAL", "EDI"]
    assert raw["vendor"]["invoice_id_after_vendor_resolution"] is True
    entry = raw["routing"]["types"]["VENDOR_SENDER_MISMATCH"]
    assert entry["raised_by"] == "VEN-04" and entry["blocking"] and entry["role"] == "OPERATIONS_ANALYST"


def test_all_five_actors_have_work(raw):
    routed = {v["role"] for v in raw["routing"]["types"].values()}
    approving = {v["role"] for v in raw["approval"]["levels"].values()}
    assert set(enums.HUMAN_ROLES) <= routed | approving
    assert raw["policy"]["owner_role"] == "PROCESS_OWNER"
    assert raw["policy"]["maintainer_role"] == "SYSTEM_ADMINISTRATOR"


def test_tolerances_are_exact_decimal_strings(raw):
    pol = load_policy()
    assert str(pol.decimal("matching", "price_tolerance_pct")) == "2.00"
    assert str(pol.decimal("matching", "over_receipt_tolerance_pct")) == "5.00"
    assert str(pol.decimal("tax", "amount_abs")) == "0.01"
    assert raw["matching"]["price_tolerance_inclusive"] is True


@pytest.mark.parametrize("mutate,needle", [
    (lambda r: r["routing"]["types"].pop("PRICE_VARIANCE"), "routing.types"),
    (lambda r: r["precedence"]["order"].reverse(), "precedence.order"),
    (lambda r: r["matching"].__setitem__("price_tolerance_pct", 2.0), "decimals must be strings"),
    (lambda r: r["routing"]["types"]["PRICE_VARIANCE"].__setitem__("blocking", False), "blocking flag"),
    (lambda r: r["routing"]["types"]["MISSING_RECEIPT"].__setitem__("queue", "NOWHERE"), "queue"),
    (lambda r: r["routing"]["types"]["TAX_CODE_MISMATCH"].__setitem__("role", "SYSTEM"), "human actor"),
    (lambda r: r["approval"]["bands"][1].__setitem__("lower_exclusive", "250000.00"), "contiguous"),
    (lambda r: r["approval"]["bands"][3].__setitem__("upper_inclusive", "9.00"), "open-ended"),
    (lambda r: r["policy"].__setitem__("version", "v1"), "MAJOR.MINOR.PATCH"),
])
def test_validator_rejects_broken_edits(raw, mutate, needle):
    broken = copy.deepcopy(raw)
    mutate(broken)
    errors = validate_policy(broken)
    assert any(needle in e for e in errors), errors


def test_load_policy_raises_on_missing_file(tmp_path):
    with pytest.raises(PolicyError):
        load_policy(tmp_path / "missing.toml")
