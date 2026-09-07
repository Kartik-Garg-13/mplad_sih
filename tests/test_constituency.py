from datetime import date

import polars as pl

from parakh.constituency import compute_constituency_scorecard

_WORKS_SCHEMA = {
    "house": pl.Utf8,
    "state": pl.Utf8,
    "constituency": pl.Utf8,
    "category": pl.Utf8,
    "sanction_amount": pl.Float64,
    "sanction_date": pl.Date,
    "completion_date": pl.Date,
}
_EXP_SCHEMA = {"house": pl.Utf8, "state": pl.Utf8, "constituency": pl.Utf8, "amount": pl.Float64}
_ALLOC_SCHEMA = {"house": pl.Utf8, "state": pl.Utf8, "constituency": pl.Utf8, "mp_name": pl.Utf8, "allocated_amount": pl.Float64}

_WORK_DEFAULT = {
    "house": "Lok Sabha",
    "state": "Bihar",
    "constituency": "PATNA",
    "category": "Street lights",
    "sanction_amount": 100_000.0,
    "sanction_date": date(2024, 1, 1),
    "completion_date": None,
}


def make_works(rows: list[dict]) -> pl.DataFrame:
    return pl.DataFrame([{**_WORK_DEFAULT, **r} for r in rows], schema=_WORKS_SCHEMA)


def make_expenditure(rows: list[dict]) -> pl.DataFrame:
    return pl.DataFrame(rows, schema=_EXP_SCHEMA) if rows else pl.DataFrame(schema=_EXP_SCHEMA)


def make_allocated(rows: list[dict]) -> pl.DataFrame:
    return pl.DataFrame(rows, schema=_ALLOC_SCHEMA)


def test_completion_rate_and_totals():
    works = make_works(
        [
            {"completion_date": date(2024, 2, 1)},
            {"completion_date": None},
            {"completion_date": None},
        ]
    )
    alloc = make_allocated([{"house": "Lok Sabha", "state": "Bihar", "constituency": "PATNA", "mp_name": "MP1", "allocated_amount": 1_000_000.0}])
    scorecard = compute_constituency_scorecard(works, make_expenditure([]), alloc)
    row = scorecard.filter(pl.col("constituency") == "PATNA")
    assert row["n_sanctioned"][0] == 3
    assert row["n_completed"][0] == 1
    assert abs(row["completion_rate"][0] - 1 / 3) < 1e-9
    assert row["total_sanctioned"][0] == 300_000.0


def test_median_days_to_complete_only_uses_completed_works():
    works = make_works(
        [
            {"sanction_date": date(2024, 1, 1), "completion_date": date(2024, 1, 11)},  # 10 days
            {"sanction_date": date(2024, 1, 1), "completion_date": date(2024, 1, 31)},  # 30 days
            {"sanction_date": date(2024, 1, 1), "completion_date": None},  # excluded
        ]
    )
    alloc = make_allocated([{"house": "Lok Sabha", "state": "Bihar", "constituency": "PATNA", "mp_name": "MP1", "allocated_amount": 1_000_000.0}])
    scorecard = compute_constituency_scorecard(works, make_expenditure([]), alloc)
    row = scorecard.filter(pl.col("constituency") == "PATNA")
    assert row["median_days_to_complete"][0] == 20.0


def test_dominant_category_and_share():
    works = make_works(
        [{"category": "Street lights"}, {"category": "Street lights"}, {"category": "Roads"}]
    )
    alloc = make_allocated([{"house": "Lok Sabha", "state": "Bihar", "constituency": "PATNA", "mp_name": "MP1", "allocated_amount": 1_000_000.0}])
    scorecard = compute_constituency_scorecard(works, make_expenditure([]), alloc)
    row = scorecard.filter(pl.col("constituency") == "PATNA")
    assert row["dominant_category"][0] == "Street lights"
    assert abs(row["dominant_category_share"][0] - 2 / 3) < 1e-9


def test_fund_utilisation_and_unspent_balance():
    works = make_works([{}])
    exp = make_expenditure([{"house": "Lok Sabha", "state": "Bihar", "constituency": "PATNA", "amount": 250_000.0}])
    alloc = make_allocated([{"house": "Lok Sabha", "state": "Bihar", "constituency": "PATNA", "mp_name": "MP1", "allocated_amount": 1_000_000.0}])
    scorecard = compute_constituency_scorecard(works, exp, alloc)
    row = scorecard.filter(pl.col("constituency") == "PATNA")
    assert row["total_expended"][0] == 250_000.0
    assert row["fund_utilisation"][0] == 0.25
    assert row["unspent_balance"][0] == 750_000.0


def test_duplicate_allocation_rows_from_mp_replacement_are_summed_not_duplicated():
    # The real case found in the corpus: a mid-term MP replacement
    # leaves a stale allocated-amount row (null) behind for the same
    # constituency alongside the current MP's real figure.
    alloc = make_allocated(
        [
            {"house": "Lok Sabha", "state": "Maharashtra", "constituency": "NANDED", "mp_name": "Old MP", "allocated_amount": None},
            {"house": "Lok Sabha", "state": "Maharashtra", "constituency": "NANDED", "mp_name": "New MP", "allocated_amount": 147_000_000.0},
        ]
    )
    works = make_works([{"state": "Maharashtra", "constituency": "NANDED"}])
    scorecard = compute_constituency_scorecard(works, make_expenditure([]), alloc)
    row = scorecard.filter(pl.col("constituency") == "NANDED")
    assert row.height == 1
    assert row["allocated_amount"][0] == 147_000_000.0


def test_rajya_sabha_works_excluded():
    works = make_works([{"house": "Rajya Sabha", "constituency": None}, {"house": "Lok Sabha"}])
    alloc = make_allocated([{"house": "Lok Sabha", "state": "Bihar", "constituency": "PATNA", "mp_name": "MP1", "allocated_amount": 1_000_000.0}])
    scorecard = compute_constituency_scorecard(works, make_expenditure([]), alloc)
    assert scorecard.filter(pl.col("constituency") == "PATNA")["n_sanctioned"][0] == 1


def test_uploaded_batch_with_a_real_constituency_is_included_regardless_of_its_house_label():
    """The scorecard keys off `constituency IS NOT NULL`, not a
    `house == "Lok Sabha"` string match — an uploaded batch (see
    uploads.py) can be labelled anything at all. A batch that
    structurally carries a real constituency (its source CSV had a
    Constituency column) must show up here even when its `house` field
    is something else entirely, exactly like a real Lok-Sabha-shaped
    upload named after the pilot it came from."""
    works = make_works([{"house": "Pilot District 2027", "state": "Kerala", "constituency": "KOTTAYAM"}])
    alloc = make_allocated(
        [{"house": "Pilot District 2027", "state": "Kerala", "constituency": "KOTTAYAM", "mp_name": "MP1", "allocated_amount": 500_000.0}]
    )
    scorecard = compute_constituency_scorecard(works, make_expenditure([]), alloc)
    row = scorecard.filter(pl.col("constituency") == "KOTTAYAM")
    assert row.height == 1
    assert row["n_sanctioned"][0] == 1


def test_a_batch_labelled_lok_sabha_with_no_real_constituency_does_not_silently_merge_in():
    """The inverse of the bug: a house *label* of "Lok Sabha" must not by
    itself pull a row into the scorecard if it has no real constituency
    (e.g. a Rajya-Sabha-shaped batch a user happened to name "Lok
    Sabha") — the old `house == "Lok Sabha"` string match would have
    silently merged it into the real Lok Sabha's aggregates."""
    works = make_works([{"house": "Lok Sabha", "state": "Kerala", "constituency": None}])
    alloc = make_allocated([])
    scorecard = compute_constituency_scorecard(works, make_expenditure([]), alloc)
    assert scorecard.height == 0
