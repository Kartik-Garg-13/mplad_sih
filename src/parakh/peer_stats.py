"""Peer-relative statistics — the one methodology every Tier B cost/time
detector shares (plan §03: "Every statistical detector is peer-relative,
and every flag states its peer group and n").

A flyover in Mumbai and a borewell in Koraput are both "works" — an
absolute outlier is meaningless, a peer-group outlier is defensible.
"""

from __future__ import annotations

import polars as pl

# Standard scaled-MAD constant (0.6745 = the 75th percentile of the
# standard normal distribution) — makes the robust z-score comparable
# in magnitude to an ordinary z-score under a roughly normal peer
# distribution, without being dragged around by the outliers a plain
# mean/stdev z-score would be.
_MAD_SCALE = 0.6745

# IQR-to-sigma constant for a standard normal distribution (the width
# between its 25th and 75th percentiles is 1.349 sigma) — used as the
# fallback spread estimate below, on the same normal-approximation
# footing as _MAD_SCALE.
_IQR_SCALE = 1.349

DEFAULT_MIN_PEER_GROUP = 30

# The floor-gated sentinel case (see below) only fires on a deviation
# this large in either direction — a judgment call, not a derived
# statistic, made explicit rather than dressed up as more rigorous
# than it is.
_DEGENERATE_FLOOR_RATIO = 2.0

# No cost within this fraction of its peer median is reported as a cost
# outlier, however many robust sigma the spread estimate makes it.
#
# Confirmed against the real corpus: MPLADS peer groups cluster so hard on
# round figures that the spread estimate can collapse to a few hundred
# rupees, and an ordinary sanction then scores as an extreme outlier — a
# Rs 4.5L work against a Rs 5.0L median came out at -17.5 sigma across 479
# peers. Worse, the flag said so in an evidence sentence reading "is 1.0x
# the peer median", which is the tool contradicting itself in the one
# sentence a reviewer is asked to trust. 73 live flags read exactly that
# way before this floor existed.
#
# Statistical significance in a near-degenerate distribution is not
# material significance, and a Tier B flag has to be worth a human's time.
# The module already accepted that principle for the fully-degenerate case
# below; this extends it to the branches that had no floor at all.
MIN_RELATIVE_DEVIATION = 0.10


def add_robust_z(
    df: pl.DataFrame,
    value_col: str,
    group_cols: list[str],
    min_n: int = DEFAULT_MIN_PEER_GROUP,
    min_relative_deviation: float = MIN_RELATIVE_DEVIATION,
) -> pl.DataFrame:
    """Add peer_n, peer_median, peer_mad, robust_z for `value_col` within
    each `group_cols` group.

    A group with fewer than `min_n` members gets a null robust_z —
    abstention, not a forced comparison against a peer group too small
    to mean anything (plan §01: "If a peer group has fewer than 30
    records, the detector abstains rather than firing on noise").

    Three tiers of spread estimate, each one a fallback for when the
    one before it is degenerate (zero) — a real MPLADS peer group
    routinely has a majority sharing one exact round-rupee figure:

    1. MAD (median absolute deviation) — the primary estimate.
    2. IQR/1.349, when MAD is zero (a bare majority, not the bulk,
       share the median) but the tails still carry real spread. This
       resolves the large majority of zero-MAD groups with a properly
       magnitude-sensitive z, rather than a flat sentinel — confirmed
       against the real corpus: without this fallback, B1 flagged
       3,172 works whose own evidence sentence stated the amount was
       within a few percent of the peer median (e.g. "1.0x the peer
       median") while calling it a >3.5-sigma outlier, because *any*
       deviation from a zero-MAD group scored an arbitrary flat 999.
    3. When IQR is *also* zero (>=75% of peers share one exact value —
       confirmed real, ~38% of zero-MAD groups): there is no spread
       estimate left to measure magnitude against, so the only
       remaining question is whether the deviation is large enough in
       plain terms to be worth a look at all. Fires only when the
       value is at least `_DEGENERATE_FLOOR_RATIO` away from the peer
       median (either direction) — small deviations abstain (null)
       rather than being reported as an extreme statistical outlier
       they are not.

    Over all three, `min_relative_deviation` is a final materiality
    gate: a value within that fraction of its peer median abstains no
    matter which estimate scored it, or how many sigma it scored. See
    MIN_RELATIVE_DEVIATION above for why.
    """
    with_stats = df.with_columns(
        pl.col(value_col).median().over(group_cols).alias("peer_median"),
        pl.len().over(group_cols).alias("peer_n"),
        pl.col(value_col).quantile(0.75).over(group_cols).alias("_peer_q75"),
        pl.col(value_col).quantile(0.25).over(group_cols).alias("_peer_q25"),
    )
    with_mad = with_stats.with_columns(
        (pl.col(value_col) - pl.col("peer_median")).abs().median().over(group_cols).alias("peer_mad"),
        (pl.col("_peer_q75") - pl.col("_peer_q25")).alias("_peer_iqr"),
    )

    deviation = pl.col(value_col) - pl.col("peer_median")
    ratio_from_median = pl.when(pl.col("peer_median") != 0).then(
        pl.col(value_col) / pl.col("peer_median")
    )
    far_from_median = (ratio_from_median >= _DEGENERATE_FLOOR_RATIO) | (
        ratio_from_median <= 1 / _DEGENERATE_FLOOR_RATIO
    )

    scored = with_mad.with_columns(
        pl.when(pl.col("peer_n") < min_n)
        .then(None)
        .when(pl.col("peer_mad") > 0)
        .then(_MAD_SCALE * deviation / pl.col("peer_mad"))
        .when(pl.col("_peer_iqr") > 0)
        .then(_MAD_SCALE * deviation / (pl.col("_peer_iqr") / _IQR_SCALE))
        .when(pl.col(value_col) == pl.col("peer_median"))
        .then(0.0)
        .when(far_from_median)
        .then(999.0)
        .otherwise(None)
        .alias("robust_z")
    )

    # The materiality floor, applied last so it gates every branch above.
    # A zero peer median is left alone: there is no relative deviation to
    # measure against, and any non-zero value there is already unbounded.
    within_floor = (
        (pl.col("peer_median") != 0)
        & ((pl.col(value_col) - pl.col("peer_median")).abs()
           < min_relative_deviation * pl.col("peer_median").abs())
    )
    return scored.with_columns(
        pl.when(within_floor).then(None).otherwise(pl.col("robust_z")).alias("robust_z")
    ).drop("_peer_q75", "_peer_q25", "_peer_iqr")
