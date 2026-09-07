"""Plan §07, method 1 — synthetic injection: "the one hard quantitative
number" for validating unsupervised detection with no real labels.

Five injector functions, one per known anomaly type, each built by
cloning a real, valid work row and mutating only the fields that
create the anomaly — every injected row keeps a real state, category,
financial year, agency and MP, so it lands in a real peer group rather
than an artificial one the detectors were never meant to police.

Each type targets one detector by construction, chosen from what's
actually built (13 detectors, no Tier C — see /methodology):

    inflated_cost          -> B1 (peer cost outlier)
    split_work             -> B5 (work splitting)
    duplicate_record       -> A3 (duplicate record)
    phantom_completion     -> A2 (phantom completion)
    agency_concentration   -> B6 (agency concentration)

"Recall" below means: did the target detector fire on this injected
row. Extra co-firing from other detectors (e.g. an inflated-cost row
also tripping B2 if it has a quantity) is left alone, not suppressed —
a real inflated cost would plausibly trip both, so a synthetic one
should too.
"""

from __future__ import annotations

from datetime import timedelta

import numpy as np
import polars as pl

INJECTED_TYPES = [
    "inflated_cost",
    "split_work",
    "duplicate_record",
    "phantom_completion",
    "agency_concentration",
]

TARGET_DETECTOR = {
    "inflated_cost": "B1",
    "split_work": "B5",
    "duplicate_record": "A3",
    "phantom_completion": "A2",
    "agency_concentration": "B6",
}

_WORK_COLUMNS = [
    "work_id", "house", "term", "state", "district_raw", "implementing_agency", "mp_name",
    "constituency", "elected_or_nominated", "category_broad", "category", "description",
    "description_corrupted", "recommended_date", "recommended_amount", "sanction_date",
    "sanction_amount", "work_status", "completion_date", "amount_disbursed_at_completion",
    "has_image_evidence", "financial_year", "quantity", "quantity_unit",
]


def inject_inflated_cost(
    works: pl.DataFrame, seed: int, n: int = 40, multiplier_range: tuple[float, float] = (10.0, 25.0)
) -> tuple[pl.DataFrame, list[str]]:
    """Clone n real, well-formed works and multiply their sanction
    (and recommended) amount far above their real peer group's median
    — B1's peer group is (category, state, financial_year), so the
    clone's untouched category/state/FY keep it in a real, sizeable
    peer group.
    """
    rng = np.random.default_rng(seed)
    candidates = works.filter(
        pl.col("work_id").str.starts_with("WS/")
        & pl.col("sanction_amount").is_not_null()
        & (pl.col("sanction_amount") > 0)
        & pl.col("category").is_not_null()
        & pl.col("state").is_not_null()
        & pl.col("financial_year").is_not_null()
    )
    anchors = candidates.sample(n=n, seed=seed, with_replacement=False).select(_WORK_COLUMNS)
    new_ids = [f"WS/SYN-INFLATED/2025-2026/{i:05d}" for i in range(n)]
    multipliers = rng.uniform(*multiplier_range, size=n)

    injected = anchors.with_columns(
        pl.Series("work_id", new_ids),
        (pl.col("sanction_amount") * pl.Series("_mult", multipliers)),
        (pl.col("recommended_amount") * pl.Series("_mult", multipliers)),
    )
    return injected, new_ids


def inject_split_work(
    works: pl.DataFrame,
    seed: int,
    n_clusters: int = 14,
    cluster_size: int = 3,
) -> tuple[pl.DataFrame, list[str]]:
    """Build n_clusters synthetic clusters, each cluster_size works
    from one real (agency, district), similarly-worded but not
    identical (TF-IDF cosine in B5's [0.85, 0.999) band — an identical
    copy-paste is excluded as legitimate boilerplate, same as B8), sized
    comparably, recommended within a 30-day window — the exact shape
    B5 looks for.
    """
    rng = np.random.default_rng(seed)
    candidates = works.filter(
        pl.col("work_id").str.starts_with("WS/")
        & pl.col("implementing_agency").is_not_null()
        & pl.col("district_raw").is_not_null()
        & pl.col("description").is_not_null()
        & (pl.col("description") != "")
        & pl.col("recommended_amount").is_not_null()
        & (pl.col("recommended_amount") > 0)
        & pl.col("recommended_date").is_not_null()
    )
    anchors = candidates.sample(n=n_clusters, seed=seed, with_replacement=False).select(_WORK_COLUMNS)

    rows: list[dict] = []
    new_ids: list[str] = []
    for cluster_i, anchor in enumerate(anchors.iter_rows(named=True)):
        base_amount = anchor["recommended_amount"]
        base_date = anchor["recommended_date"]
        for member_i in range(cluster_size):
            work_id = f"WS/SYN-SPLIT/2025-2026/{cluster_i:03d}{member_i:02d}"
            new_ids.append(work_id)
            row = dict(anchor)
            row["work_id"] = work_id
            row["description"] = f"{anchor['description']} - Site {member_i + 1}"
            row["recommended_amount"] = base_amount * rng.uniform(0.85, 1.15)
            row["sanction_amount"] = row["recommended_amount"]
            row["recommended_date"] = base_date + timedelta(days=int(rng.integers(-14, 15)))
            row["completion_date"] = None
            row["work_status"] = "Sanction"
            rows.append(row)

    injected = pl.DataFrame(rows, schema=anchors.schema)
    return injected, new_ids


def inject_duplicate_record(works: pl.DataFrame, seed: int, n: int = 40) -> tuple[pl.DataFrame, list[str]]:
    """Duplicate n real work_ids verbatim — A3's whole check. The
    current corpus has zero literal duplicate work_ids (checked before
    writing this), so any real id sampled here is a clean injection,
    not a pre-existing one the detector would have fired on anyway.
    """
    candidates = works.filter(pl.col("work_id").str.starts_with("WS/")).select(_WORK_COLUMNS)
    anchors = candidates.sample(n=n, seed=seed, with_replacement=False)
    return anchors, anchors["work_id"].to_list()


def inject_phantom_completion(works: pl.DataFrame, seed: int, n: int = 40) -> tuple[pl.DataFrame, list[str]]:
    """Clone n real works, mark them Work Completed with a real
    sanction amount and no expenditure rows appended for their new ids
    — A2's exact trigger. No expenditure needs to be touched: expenditure
    is joined by work_id, and a fresh synthetic id simply has none.
    """
    candidates = works.filter(
        pl.col("work_id").str.starts_with("WS/")
        & pl.col("sanction_amount").is_not_null()
        & (pl.col("sanction_amount") > 0)
        & pl.col("sanction_date").is_not_null()
    )
    anchors = candidates.sample(n=n, seed=seed, with_replacement=False).select(_WORK_COLUMNS)
    new_ids = [f"WS/SYN-PHANTOM/2025-2026/{i:05d}" for i in range(n)]

    injected = anchors.with_columns(
        pl.Series("work_id", new_ids),
        pl.lit("Work Completed").alias("work_status"),
        (pl.col("sanction_date") + pl.duration(days=10)).alias("completion_date"),
        pl.lit(0.0).alias("amount_disbursed_at_completion"),
    )
    return injected, new_ids


def _find_concentration_target(works: pl.DataFrame, min_works_per_mp: int = 10) -> tuple[str, str]:
    """The simplest eligible MP to inject into: fewest existing
    agencies (ties broken by lowest current top-agency share) among
    MPs with >=2 agencies and >=min_works_per_mp works.

    Checked against the real corpus before fixing on this rule: an
    MP's raw *share* alone is a bad ranking key — the globally most-
    "balanced" MP by share is typically balanced because they spread
    work across a dozen-plus agencies, not two, so a fixed-size
    injection barely moves their share (confirmed: one such MP, 23
    agencies, moved from 9.8% to 25.9% on a 20-work injection, nowhere
    near the ~96th-percentile flag threshold). Fewest agencies first
    picks a two-or-three-agency MP instead, where the same injection
    has real leverage.
    """
    sanctioned = works.filter(
        pl.col("sanction_amount").is_not_null()
        & pl.col("implementing_agency").is_not_null()
        & pl.col("mp_name").is_not_null()
    )
    by_mp_agency = sanctioned.group_by(["mp_name", "implementing_agency"]).agg(
        pl.col("sanction_amount").sum().alias("agency_total"),
    )
    mp_totals = by_mp_agency.group_by("mp_name").agg(
        pl.col("agency_total").sum().alias("mp_total"),
        pl.len().alias("n_agencies"),
    )
    shares = by_mp_agency.join(mp_totals, on="mp_name").with_columns(
        (pl.col("agency_total") / pl.col("mp_total")).alias("share")
    )
    n_works_by_mp = dict(
        sanctioned.group_by("mp_name").agg(pl.len().alias("n")).iter_rows()
    )
    top_per_mp = (
        shares.filter(pl.col("n_agencies") >= 2)
        .sort("share", descending=True)
        .group_by("mp_name")
        .first()
        .with_columns(
            pl.col("mp_name").replace_strict(n_works_by_mp, default=0).alias("n_works")
        )
        .filter(pl.col("n_works") >= min_works_per_mp)
        .sort(["n_agencies", "share"])
    )
    top = top_per_mp.row(0, named=True)
    return top["mp_name"], top["implementing_agency"]


def inject_agency_concentration(
    works: pl.DataFrame, seed: int, n: int = 20, target_share_multiplier: float = 40.0
) -> tuple[pl.DataFrame, list[str]]:
    """Pick the target MP/agency and route n new works to that agency,
    sized so their combined value is `target_share_multiplier` times
    the MP's current total sanctioned value — not a fixed rupee
    amount. A fixed size is fragile (it depends entirely on how large
    the MP's existing total happens to be); scaling relative to that
    total guarantees the post-injection share lands close to
    multiplier/(multiplier+1) regardless of the MP picked (e.g. 40 ->
    ~97.6%), comfortably past B6's ~96th-percentile real threshold.
    """
    mp_name, agency = _find_concentration_target(works)
    mp_rows = works.filter((pl.col("mp_name") == mp_name) & pl.col("sanction_amount").is_not_null())
    mp_total = mp_rows["sanction_amount"].sum() or 0.0

    anchor_pool = works.filter(
        (pl.col("mp_name") == mp_name)
        & (pl.col("implementing_agency") == agency)
        & pl.col("work_id").str.starts_with("WS/")
    )
    if anchor_pool.height == 0:
        anchor_pool = mp_rows
    anchor = anchor_pool.select(_WORK_COLUMNS).row(0, named=True)

    rng = np.random.default_rng(seed)
    total_to_inject = max(mp_total, 500_000.0) * target_share_multiplier
    per_work_amount = total_to_inject / n
    new_ids = [f"WS/SYN-CONCENTRATE/2025-2026/{i:05d}" for i in range(n)]
    rows = []
    for i, work_id in enumerate(new_ids):
        row = dict(anchor)
        row["work_id"] = work_id
        row["implementing_agency"] = agency
        row["mp_name"] = mp_name
        row["sanction_amount"] = per_work_amount * rng.uniform(0.9, 1.1)
        row["recommended_amount"] = row["sanction_amount"]
        rows.append(row)

    injected = pl.DataFrame(rows, schema=[(c, works.schema[c]) for c in _WORK_COLUMNS])
    return injected, new_ids


def build_synthetic_corpus(works: pl.DataFrame, seed: int = 20260904) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Injects all five types into a copy of `works`. Returns
    (augmented_works, ground_truth) where ground_truth has one row per
    injected work_id: [work_id, injected_type, target_detector].
    """
    injectors = {
        "inflated_cost": lambda: inject_inflated_cost(works, seed),
        "split_work": lambda: inject_split_work(works, seed + 1),
        "duplicate_record": lambda: inject_duplicate_record(works, seed + 2),
        "phantom_completion": lambda: inject_phantom_completion(works, seed + 3),
        "agency_concentration": lambda: inject_agency_concentration(works, seed + 4),
    }

    all_injected = [works.select(_WORK_COLUMNS)]
    ground_truth_rows: list[dict] = []
    for injected_type, fn in injectors.items():
        injected_df, ids = fn()
        all_injected.append(injected_df.select(_WORK_COLUMNS))
        for work_id in ids:
            ground_truth_rows.append(
                {"work_id": work_id, "injected_type": injected_type, "target_detector": TARGET_DETECTOR[injected_type]}
            )

    augmented = pl.concat(all_injected, how="vertical_relaxed")
    ground_truth = pl.DataFrame(ground_truth_rows)
    return augmented, ground_truth
