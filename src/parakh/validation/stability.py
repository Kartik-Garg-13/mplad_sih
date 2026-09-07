"""Plan §07, method 4 — stability: "bootstrap-resample the corpus and
measure rank correlation... across runs."

The plan's original wording targeted the Review Priority Score (Tier
C's C3) — a single composite rank per work. That was never built (see
/methodology): there is no composite score to bootstrap. The closest
honest analogue that exists is Tier B's own peer-relative thresholds
(a percentile or robust z-score cutoff, recomputed from the sample
every time) — do those cutoffs, and the set of works that cross them,
hold up under resampling noise, or are they an artifact of exactly
this one corpus?

Scoped to six of Tier B's eight detectors — B1, B2, B3, B4, B6, B7 —
all of which reduce to a statistic over a peer group (median/MAD,
percentile, national share). B5 and B8 are deliberately excluded: both
are TF-IDF description-similarity detectors, and bootstrap-with-
replacement duplicates rows verbatim, which makes two resampled copies
of the *same* real work look like a near-duplicate pair to a text-
similarity detector — an artifact of the resampling method itself, not
a statement about whether the underlying detector is stable. Tier A is
excluded outright: its checks are deterministic pass/fail on a single
row (a ledger contradiction either holds or it doesn't) with no
threshold fitted to the sample, so there is nothing for resampling to
destabilize.
"""

from __future__ import annotations

import math

import polars as pl

from parakh.detectors.tier_b import (
    b1_peer_cost_outlier,
    b2_cost_per_unit_outlier,
    b3_stalled_work,
    b4_threshold_bunching,
    b6_agency_concentration,
    b7_year_end_bunching,
)

_STABILITY_DETECTORS = {
    "B1": b1_peer_cost_outlier,
    "B2": b2_cost_per_unit_outlier,
    "B3": b3_stalled_work,
    "B4": b4_threshold_bunching,
    "B6": b6_agency_concentration,
    "B7": b7_year_end_bunching,
}


def _jaccard(a: set, b: set) -> float:
    union = a | b
    return len(a & b) / len(union) if union else 1.0


# A same-size bootstrap resample only ever contains ~1 - 1/e (~63.2%)
# of the corpus's distinct rows — the rest are simply absent from that
# draw, whatever the detector does. So even a perfectly stable
# detector cannot score a Jaccard overlap anywhere near 1.0 against
# the un-resampled baseline; ~0.63 is closer to the practical ceiling.
# Reported here so a detector's raw score isn't misread against 1.0.
BOOTSTRAP_RETENTION_CEILING = round(1 - 1 / math.e, 4)


def bootstrap_stability(
    works: pl.DataFrame,
    expenditure: pl.DataFrame,
    n_bootstrap: int = 10,
    seed: int = 20260904,
) -> dict:
    """For each of the six eligible detectors: run once on the real
    corpus (baseline), then n_bootstrap times on a same-size resample
    drawn with replacement, and report the mean Jaccard overlap between
    each resample's flagged-work set and the baseline's.

    A detector near 1.0 flags essentially the same works regardless of
    which exact sample it saw — a threshold that reflects a real
    pattern, not sampling noise. A detector far below 1.0 is telling
    you its threshold is fragile at this peer-group size, which is
    itself a useful, honest finding to report, not to hide.
    """
    results: dict = {"_retention_ceiling": BOOTSTRAP_RETENTION_CEILING}
    for name, fn in _STABILITY_DETECTORS.items():
        baseline = set(fn(works, expenditure)["work_id"].to_list())
        overlaps = []
        for i in range(n_bootstrap):
            resample = works.sample(n=works.height, with_replacement=True, seed=seed + i)
            flagged = set(fn(resample, expenditure)["work_id"].to_list())
            overlaps.append(_jaccard(baseline, flagged))
        results[name] = {
            "baseline_n_flagged": len(baseline),
            "n_bootstrap": n_bootstrap,
            "mean_jaccard_vs_baseline": round(sum(overlaps) / len(overlaps), 4),
            "min_jaccard_vs_baseline": round(min(overlaps), 4),
            "max_jaccard_vs_baseline": round(max(overlaps), 4),
        }
    return results


if __name__ == "__main__":
    import polars as pl

    from parakh.config import PROCESSED_DIR

    _works = pl.read_parquet(PROCESSED_DIR / "works.parquet")
    _expenditure = pl.read_parquet(PROCESSED_DIR / "expenditure.parquet")
    _result = bootstrap_stability(_works, _expenditure)

    print(f"bootstrap retention ceiling (structural, not detector-specific): {_result['_retention_ceiling']:.3f}")
    print()
    print(f"{'detector':<6}{'baseline_n':>12}{'mean_jaccard':>14}{'min':>8}{'max':>8}")
    for name, r in _result.items():
        if name.startswith("_"):
            continue
        print(
            f"{name:<6}{r['baseline_n_flagged']:>12}{r['mean_jaccard_vs_baseline']:>14.3f}"
            f"{r['min_jaccard_vs_baseline']:>8.3f}{r['max_jaccard_vs_baseline']:>8.3f}"
        )
