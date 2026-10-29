"""Deterministic random streams (ADR-015).

Every concern gets its own random.Random seeded by sha256(f"{seed}:{name}"), so adding draws to
one stream never shifts another. Only integer draws (randrange, shuffle) are used; continuous
values are built from integers with Decimal arithmetic (including Decimal.exp), never from
platform libm functions.
"""
from __future__ import annotations

import bisect
import hashlib
import random
from decimal import Decimal, localcontext
from typing import Sequence, TypeVar

T = TypeVar("T")
_SCALE = 1_000_000


def stream(seed: int, name: str) -> random.Random:
    digest = hashlib.sha256(f"{seed}:{name}".encode("utf-8")).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def between(rng: random.Random, low: int, high: int) -> int:
    """Uniform integer in [low, high]."""
    return low + rng.randrange(high - low + 1)


def weighted_index(rng: random.Random, weights: Sequence[int]) -> int:
    """Index drawn with integer weights (exact cumulative sums, no floats)."""
    cumulative, total = [], 0
    for w in weights:
        if w < 0:
            raise ValueError("weights must be >= 0")
        total += w
        cumulative.append(total)
    if total <= 0:
        raise ValueError("at least one weight must be > 0")
    return bisect.bisect_right(cumulative, rng.randrange(total))


def weighted_choice(rng: random.Random, items: Sequence[T], weights: Sequence[int]) -> T:
    return items[weighted_index(rng, weights)]


def shuffled(rng: random.Random, items: Sequence[T]) -> list[T]:
    out = list(items)
    rng.shuffle(out)
    return out


def uniform_decimal(rng: random.Random, low: str, high: str, places: int = 4) -> Decimal:
    """Uniform Decimal in [low, high] on a grid of 10^-places."""
    q = Decimal(1).scaleb(-places)
    lo, hi = int(Decimal(low) / q), int(Decimal(high) / q)
    return Decimal(between(rng, lo, hi)) * q


def standard_normal(rng: random.Random) -> Decimal:
    """Irwin-Hall(12) approximation of N(0, 1): sum of 12 uniforms minus 6, in exact Decimal."""
    total = sum(rng.randrange(_SCALE) for _ in range(12))
    return Decimal(total) / _SCALE - 6


def lognormal(rng: random.Random, median: Decimal, sigma: Decimal) -> Decimal:
    """median x exp(sigma x Z), computed with Decimal.exp at fixed precision."""
    with localcontext() as ctx:
        ctx.prec = 28
        return median * (sigma * standard_normal(rng)).exp()
