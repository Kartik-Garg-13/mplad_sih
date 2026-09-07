"""Detector registry.

Every detector is a pure function `(works, expenditure) -> pl.DataFrame`
with the common flag schema [work_id, detector, tier, evidence] (see
tier_a.py's module docstring for the contract). `run_all` stacks every
registered detector's output into one flags table — nothing else in
the codebase should call an individual detector directly except tests,
so adding a detector to REGISTRY is the only step needed to wire it in.
"""

from __future__ import annotations

import polars as pl

from parakh.detectors import tier_a, tier_b

REGISTRY: dict[str, callable] = {
    "A1": tier_a.a1_ledger_contradiction,
    "A2": tier_a.a2_phantom_completion,
    "A3": tier_a.a3_duplicate_record,
    "A4": tier_a.a4_orphan_sanction,
    "A5": tier_a.a5_unverified_completion,
    "B1": tier_b.b1_peer_cost_outlier,
    "B2": tier_b.b2_cost_per_unit_outlier,
    "B3": tier_b.b3_stalled_work,
    "B4": tier_b.b4_threshold_bunching,
    "B5": tier_b.b5_work_splitting,
    "B6": tier_b.b6_agency_concentration,
    "B7": tier_b.b7_year_end_bunching,
    "B8": tier_b.b8_near_duplicate_funding,
}


def run_all(works: pl.DataFrame, expenditure: pl.DataFrame) -> pl.DataFrame:
    frames = [fn(works, expenditure) for fn in REGISTRY.values()]
    non_empty = [f for f in frames if f.height > 0]
    if not non_empty:
        return tier_a.EMPTY_FLAGS.clone()
    return pl.concat(non_empty, how="vertical_relaxed")
