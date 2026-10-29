"""Exact decimal arithmetic for money, quantities and percentages.

Rules (ADR-014): money is Decimal quantised to 0.01 with ROUND_HALF_UP; quantities are quantised to
the precision of their unit of measure; binary floats never touch money. Values cross file
boundaries as canonical strings ("1234.50"), never as floats.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from .enums import UOM_DECIMALS

CENT = Decimal("0.01")
ZERO = Decimal("0")
HUNDRED = Decimal("100")


def D(value: str | int | Decimal) -> Decimal:
    """Parse an exact Decimal. Floats are rejected on purpose."""
    if isinstance(value, float):
        raise TypeError("binary floats are not allowed for money or quantities")
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value).strip())
    except InvalidOperation as exc:
        raise ValueError(f"not a decimal: {value!r}") from exc


def money(value: str | int | Decimal) -> Decimal:
    """Quantise to cents, half up."""
    return D(value).quantize(CENT, rounding=ROUND_HALF_UP)


def qty(value: str | int | Decimal, uom: str) -> Decimal:
    """Quantise a quantity to the precision of its unit of measure."""
    places = UOM_DECIMALS[uom]
    return D(value).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)


def line_net(quantity: Decimal, unit_price: Decimal) -> Decimal:
    """Line extension: round_half_up(quantity x unit price, 2)."""
    return money(quantity * unit_price)


def tax_amount(net: Decimal, rate_pct: Decimal) -> Decimal:
    """Line tax: round_half_up(net x rate / 100, 2). Tax is computed per line, then summed."""
    return money(net * rate_pct / HUNDRED)


def pct_change(actual: Decimal, reference: Decimal) -> Decimal:
    """Signed percentage variance of actual against reference, exact (not rounded)."""
    if reference == ZERO:
        raise ZeroDivisionError("reference value is zero")
    return (actual - reference) * HUNDRED / reference


def within_pct(actual: Decimal, reference: Decimal, tolerance_pct: Decimal) -> bool:
    """Inclusive tolerance test |actual - reference| <= reference x tolerance% (no rounding)."""
    return abs(actual - reference) * HUNDRED <= abs(reference) * tolerance_pct


def fmt(value: Decimal, places: int = 2) -> str:
    """Canonical text form used in CSV, JSON and SQL output."""
    return f"{value.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP):f}"


def round_half_up_int(numerator: int, denominator: int) -> int:
    """Integer round-half-up of numerator/denominator for non-negative integers (no floats)."""
    if denominator <= 0 or numerator < 0:
        raise ValueError("expects numerator >= 0 and denominator > 0")
    return (2 * numerator + denominator) // (2 * denominator)
