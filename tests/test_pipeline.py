"""Schema and integrity tests against the real raw exports.

These run the actual ingestion (not synthetic data) and check the
invariants the plan calls out explicitly: no silent amount-magnitude
corruption, no duplicate IDs where uniqueness is assumed, row counts
in the range confirmed during recon, and unparseable rows visible
rather than dropped. If one of these fails, a detector downstream is
about to be built on a wrong assumption — that's the point of catching
it here.
"""

import polars as pl
import pytest

from parakh.config import UNPARSEABLE_WORK_ID, UNSANCTIONED_WORK_ID
from parakh import config
from parakh.ingest import load_stage_both_houses
from parakh.pipeline import (
    build_allocated_table,
    build_calamity_table,
    build_expenditure_table,
    build_works_table,
)

# Row counts confirmed against the eSAKSHI dashboard's own published
# totals during recon (§01 of the plan) — a generous band, not an exact
# match, since the live portal keeps accruing new works between pulls.
_EXPECTED_RANGES = {
    "recommended": (125_000, 140_000),
    "sanctioned": (95_000, 105_000),
    "completed": (40_000, 50_000),
    "expenditure": (100_000, 115_000),
}


# These assert the integrity of the shipped eSAKSHI corpus, so they load the
# built-in house/terms explicitly. Without the narrowing, adding a dataset
# through the upload page would fail the suite — the counts would climb out of
# the expected band and a third house name would appear — which would be the
# test reporting a user's legitimate action as a regression.
BUILTIN = tuple(config.HOUSE_TERMS)


@pytest.mark.parametrize("stage", ["recommended", "sanctioned", "completed", "expenditure"])
def test_row_counts_in_expected_range(stage):
    df = load_stage_both_houses(stage, houses=BUILTIN)
    lo, hi = _EXPECTED_RANGES[stage]
    assert lo <= df.height <= hi, (
        f"{stage}: {df.height} rows, expected {lo}-{hi} — "
        "either the raw files changed or a loader is silently dropping/duplicating rows"
    )


def test_both_houses_present_in_every_stage():
    for stage in _EXPECTED_RANGES:
        houses = set(load_stage_both_houses(stage, houses=BUILTIN)["house"].unique().to_list())
        assert houses == {"Lok Sabha", "Rajya Sabha"}, f"{stage}: got houses {houses}"


def test_work_id_genuine_parse_failure_rate_is_small():
    """Genuinely unparseable IDs (neither the WS/MP.../seq pattern nor
    the "NA" not-yet-sanctioned placeholder) should be rare. A large
    rate here means the ID regex broke against real data."""
    recommended = load_stage_both_houses("recommended", houses=BUILTIN)
    failure_rate = (recommended["work_id"] == UNPARSEABLE_WORK_ID).mean()
    assert failure_rate < 0.01, f"{failure_rate:.2%} of work IDs were genuinely unparseable"


def test_unsanctioned_work_id_rate_matches_expected_funnel_shape():
    """~25% of Recommended rows have no work ID yet (confirmed: 100%
    correlated with an empty Sanction Date — an ID is only allotted at
    sanction time). A wildly different rate means either the raw data
    changed a lot since recon, or the sentinel logic broke."""
    recommended = load_stage_both_houses("recommended", houses=BUILTIN)
    unsanctioned_rate = (recommended["work_id"] == UNSANCTIONED_WORK_ID).mean()
    assert 0.10 < unsanctioned_rate < 0.45, (
        f"{unsanctioned_rate:.2%} of works have no ID yet — outside the sane band; "
        "re-check the Sanction Date correlation before trusting this"
    )
    # The correlation itself, not just the rate.
    unsanctioned = recommended.filter(pl.col("work_id") == UNSANCTIONED_WORK_ID)
    assert unsanctioned["Sanction Date"].null_count() == unsanctioned.height


def test_works_table_no_duplicate_work_ids():
    works = build_works_table()
    real_ids = works.filter(
        ~pl.col("work_id").is_in([UNPARSEABLE_WORK_ID, UNSANCTIONED_WORK_ID])
    )
    assert real_ids.height == real_ids["work_id"].n_unique()


def test_amounts_are_positive_rupees_not_lakhs_or_crores():
    """A ₹5cr/year scheme: individual work amounts should sit well
    under that ceiling. If this fails, a unit-magnitude mistake
    (lakhs vs rupees) has silently entered the pipeline — see the plan's
    risk register."""
    works = build_works_table()
    amounts = works["sanction_amount"].drop_nulls()
    assert amounts.min() >= 0
    assert amounts.max() < 50_00_00_000  # ₹50 crore — generous ceiling, not a real ceiling


def test_sanction_date_never_before_recommended_date():
    works = build_works_table()
    both_present = works.filter(
        pl.col("recommended_date").is_not_null() & pl.col("sanction_date").is_not_null()
    )
    violations = both_present.filter(pl.col("sanction_date") < pl.col("recommended_date"))
    # Not asserting zero — a handful of backdated entries in real
    # government data is plausible — but flag if it becomes common,
    # since this is exactly the ledger-contradiction shape detector A1
    # looks for.
    rate = violations.height / both_present.height if both_present.height else 0
    assert rate < 0.02, f"{rate:.2%} of works have sanction before recommendation"


def test_expenditure_transactions_reference_known_work_ids():
    works = build_works_table()
    expenditure = build_expenditure_table()
    known_ids = set(works["work_id"].to_list())
    orphaned = expenditure.filter(~pl.col("work_id").is_in(known_ids))
    rate = orphaned.height / expenditure.height
    assert rate < 0.05, (
        f"{rate:.2%} of expenditure rows reference a work_id absent from the works table — "
        "check the join key, not just this test"
    )


def test_allocated_and_calamity_tables_load():
    assert build_allocated_table().height > 0
    assert build_calamity_table().height > 0


def test_category_column_is_the_fine_grained_one_not_the_coarse_one():
    """The dedicated "Work category" source column is ~98% "Normal/Others"
    in real data — useless for peer-grouping. The usable taxonomy lives
    in the text parsed out of the work ID field. `category` must be
    that one; if this regresses back to the coarse field, every B1/B2-
    style peer-relative detector silently loses its grouping key."""
    works = build_works_table()
    top_share = (
        works["category"].value_counts(sort=True).row(0)[1] / works.height
    )
    assert top_share < 0.5, (
        f"top category value covers {top_share:.0%} of rows — "
        "`category` looks like the coarse, near-constant field again"
    )
