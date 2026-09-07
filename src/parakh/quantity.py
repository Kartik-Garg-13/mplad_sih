"""Quantity extraction from free-text work descriptions — the enrichment
step B2 (cost-per-unit) depends on.

Checked against the real corpus before designing this (the plan's own
"1.5 km CC road" example was an invented illustration, not something
observed in real data): MPLADS descriptions are overwhelmingly location
narratives — "from X's house to Y's house", "near Durga Temple" — not
quantity specifications. Measured pattern frequency across all 131K
non-corrupted descriptions:

    N nos/no.s        2.7%
    X meter/mtr        4.2% (8.1% within road descriptions specifically)
    Capacity N Ltrs    0.5%
    X km                0.1% (roads almost never state km; meters, when
                               present, are the real unit in use)
    X feet/ft           0.5%

Only the first three are shipped — each was spot-checked against real
description text and confirmed semantically correct where it fires
(e.g. "developement lenght 400 meters by 7 meter" is a real road
length, not a coincidental number). "X km" and "X feet" weren't worth
a separate pattern at these rates. Real, honest coverage is reported
by the detector, not invented — see tier_b.b2_cost_per_unit_outlier.
"""

from __future__ import annotations

import polars as pl

_ROAD_CATEGORY_PREFIX = "Construction of roads"

_ROAD_LENGTH_PATTERN = r"(?i)(\d+(?:\.\d+)?)\s*(?:meter|metre|mtr)s?\b"
_COUNT_PATTERN = r"(?i)\b(\d+)\s*nos?\.?\b"
_CAPACITY_LITRES_PATTERN = r"(?i)capacity.{0,15}?(\d+(?:\.\d+)?)\s*(?:ltrs?|litres?|liters?)\b"


def extract_quantity(category_col: str = "category", description_col: str = "description") -> list[pl.Expr]:
    """Add `quantity` (Float64) and `quantity_unit` (Utf8) columns.

    Tries, in order: road length in meters (road category only), an
    explicit "N nos" count (any category), a stated capacity in litres
    (any category — the phrasing itself is specific enough not to need
    a category restriction). First match wins; no match leaves both
    columns null, which is the honest, expected outcome for the large
    majority of rows.
    """
    desc = pl.col(description_col)
    is_road = pl.col(category_col).str.starts_with(_ROAD_CATEGORY_PREFIX)

    road_length = desc.str.extract(_ROAD_LENGTH_PATTERN, 1).cast(pl.Float64, strict=False)
    count = desc.str.extract(_COUNT_PATTERN, 1).cast(pl.Float64, strict=False)
    capacity = desc.str.extract(_CAPACITY_LITRES_PATTERN, 1).cast(pl.Float64, strict=False)

    quantity = (
        pl.when(is_road & road_length.is_not_null())
        .then(road_length)
        .when(count.is_not_null())
        .then(count)
        .when(capacity.is_not_null())
        .then(capacity)
        .otherwise(None)
        .alias("quantity")
    )
    unit = (
        pl.when(is_road & road_length.is_not_null())
        .then(pl.lit("meter"))
        .when(count.is_not_null())
        .then(pl.lit("unit"))
        .when(capacity.is_not_null())
        .then(pl.lit("litre"))
        .otherwise(None)
        .alias("quantity_unit")
    )
    return [quantity, unit]
