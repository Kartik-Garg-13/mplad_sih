"""Precomputed peer-group histograms for B1 and B3's evidence cards.

Tier B currently *asserts* its peer comparison in prose ("4.2x the peer
median (n=151)") without ever showing the distribution that sentence is
about. This module builds exactly that: for every peer group large enough
for B1 or B3 to actually fire (the same >=30 floor, the same grouping
columns — see peer_stats.py and detectors/tier_b.py), a histogram of the
real values in that group, so a work's own position can be drawn against
it rather than just described.

Built once here at database-rebuild time, not computed per-request: the
eligible-group count is small enough that this is cheap (519 B1 groups,
209 B3 groups on the current corpus — confirmed by direct measurement,
well under the corpus's own 131K works), and it keeps the same "nothing
computes a detector live" guarantee every other table in this database
already holds.
"""

from __future__ import annotations

import numpy as np
import polars as pl

from parakh.peer_stats import DEFAULT_MIN_PEER_GROUP

NUM_BUCKETS = 12

# Joins a group's key columns into one lookup string. \x1f (ASCII "unit
# separator") rather than a printable delimiter like "|" or "-" — both of
# those appear inside real category and state text in this corpus, and a
# delimiter that can also appear in the data it's separating is exactly
# the kind of bug that only shows up on a work whose category happens to
# contain it.
_KEY_SEP = "\x1f"


def group_key(*parts: str) -> str:
    return _KEY_SEP.join(parts)


def _build_one(
    df: pl.DataFrame,
    detector: str,
    value_col: str,
    group_cols: list[str],
    min_n: int = DEFAULT_MIN_PEER_GROUP,
) -> pl.DataFrame:
    counts = df.group_by(group_cols).agg(pl.len().alias("n"))
    eligible_keys = counts.filter(pl.col("n") >= min_n)
    eligible = df.join(eligible_keys.select(group_cols), on=group_cols, how="inner")

    rows: list[dict] = []
    for key_vals, group in eligible.group_by(group_cols, maintain_order=True):
        values = group[value_col].drop_nulls().to_numpy()
        n = len(values)
        if n == 0:
            continue
        median = float(np.median(values))
        lo, hi = float(values.min()), float(values.max())
        if hi > lo:
            edges = np.linspace(lo, hi, NUM_BUCKETS + 1)
            bucket_counts, _ = np.histogram(values, bins=edges)
        else:
            # Every peer shares one exact value — a single bucket spanning
            # it, rather than dividing by zero building a range that
            # doesn't exist.
            edges = np.array([lo, lo + 1.0])
            bucket_counts = np.array([n])
        rows.append(
            {
                "detector": detector,
                "group_key": group_key(*(str(v) for v in key_vals)),
                "n": n,
                "median": median,
                "bucket_edges": edges.tolist(),
                "bucket_counts": bucket_counts.tolist(),
            }
        )

    schema = {
        "detector": pl.Utf8,
        "group_key": pl.Utf8,
        "n": pl.Int64,
        "median": pl.Float64,
        "bucket_edges": pl.List(pl.Float64),
        "bucket_counts": pl.List(pl.Int64),
    }
    return pl.DataFrame(rows, schema=schema) if rows else pl.DataFrame(schema=schema)


def build_peer_distributions(works: pl.DataFrame) -> pl.DataFrame:
    """One row per eligible (detector, peer group) — see module docstring.

    B1's group is category x state x financial_year on `sanction_amount`;
    B3's is category x state on `days_to_complete`, computed only from
    works that have actually completed (an open work has no completion
    time to contribute to the distribution it's later compared against —
    exactly what b3_stalled_work itself does).
    """
    b1_input = works.filter(
        pl.col("sanction_amount").is_not_null()
        & pl.col("category").is_not_null()
        & pl.col("state").is_not_null()
        & pl.col("financial_year").is_not_null()
    )
    b1 = _build_one(b1_input, "B1", "sanction_amount", ["category", "state", "financial_year"])

    b3_input = works.filter(
        pl.col("sanction_date").is_not_null()
        & pl.col("completion_date").is_not_null()
        & pl.col("category").is_not_null()
        & pl.col("state").is_not_null()
    ).with_columns(
        (pl.col("completion_date") - pl.col("sanction_date")).dt.total_days().alias("days_to_complete")
    )
    b3 = _build_one(b3_input, "B3", "days_to_complete", ["category", "state"])

    return pl.concat([b1, b3], how="vertical_relaxed")
