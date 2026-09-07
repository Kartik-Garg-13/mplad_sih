from datetime import date

import polars as pl

from parakh.stall_model import _add_features, _category_thresholds, build_dataset

_SCHEMA = {
    "work_id": pl.Utf8,
    "category": pl.Utf8,
    "state": pl.Utf8,
    "implementing_agency": pl.Utf8,
    "mp_name": pl.Utf8,
    "financial_year": pl.Utf8,
    "sanction_amount": pl.Float64,
    "sanction_date": pl.Date,
    "completion_date": pl.Date,
    "description": pl.Utf8,
    "description_corrupted": pl.Boolean,
}

_DEFAULT = {
    "work_id": "W1",
    "category": "Street lights",
    "state": "Bihar",
    "implementing_agency": "AGENCY_A",
    "mp_name": "MP1",
    "financial_year": "2024-2025",
    "sanction_amount": 100_000.0,
    "sanction_date": date(2024, 1, 1),
    "completion_date": None,
    "description": "Installation of street lights",
    "description_corrupted": False,
}


def make_works(rows: list[dict]) -> pl.DataFrame:
    full = [{**_DEFAULT, **r} for r in rows]
    return pl.DataFrame(full, schema=_SCHEMA)


def test_category_thresholds_requires_min_n():
    rows = [
        {"work_id": f"W{i}", "sanction_date": date(2024, 1, 1), "completion_date": date(2024, 1, 11)}
        for i in range(10)
    ]  # below MIN_CATEGORY_N=30
    works = make_works(rows)
    thresholds = _category_thresholds(works)
    assert thresholds.height == 0


def test_category_thresholds_computed_for_large_enough_category():
    rows = [
        {"work_id": f"W{i}", "category": "Street lights", "sanction_date": date(2024, 1, 1), "completion_date": date(2024, 1, 31)}
        for i in range(30)
    ]
    works = make_works(rows)
    thresholds = _category_thresholds(works)
    assert thresholds.height == 1
    assert thresholds["p75_days"][0] == 30.0


def test_completed_work_labeled_slow_when_over_threshold():
    peers = [
        {"work_id": f"P{i}", "sanction_date": date(2024, 1, 1), "completion_date": date(2024, 1, 31)}
        for i in range(30)
    ]  # P75 = 30 days
    slow_work = {"work_id": "SLOW", "sanction_date": date(2024, 1, 1), "completion_date": date(2024, 4, 1)}  # ~90 days
    works = make_works(peers + [slow_work])
    dataset = build_dataset(works, as_of=date(2024, 12, 1))
    labeled = dataset["labeled"]
    assert labeled.filter(pl.col("work_id") == "SLOW")["label"][0] == 1


def test_in_progress_past_threshold_is_confirmed_stalled():
    peers = [
        {"work_id": f"P{i}", "sanction_date": date(2024, 1, 1), "completion_date": date(2024, 1, 31)}
        for i in range(30)
    ]  # P75 = 30 days
    stalled_open = {"work_id": "STALLED_OPEN", "sanction_date": date(2024, 1, 1), "completion_date": None}
    works = make_works(peers + [stalled_open])
    # as_of far beyond the threshold -> confirmed stalled
    dataset = build_dataset(works, as_of=date(2024, 6, 1))
    labeled = dataset["labeled"]
    assert labeled.filter(pl.col("work_id") == "STALLED_OPEN")["label"][0] == 1
    assert dataset["score"].filter(pl.col("work_id") == "STALLED_OPEN").height == 0


def test_in_progress_within_window_is_censored_not_labeled():
    peers = [
        {"work_id": f"P{i}", "sanction_date": date(2024, 1, 1), "completion_date": date(2024, 1, 31)}
        for i in range(30)
    ]  # P75 = 30 days
    recent_open = {"work_id": "RECENT_OPEN", "sanction_date": date(2024, 5, 20), "completion_date": None}
    works = make_works(peers + [recent_open])
    # as_of only 5 days after sanction -> well within the 30-day window
    dataset = build_dataset(works, as_of=date(2024, 5, 25))
    labeled = dataset["labeled"]
    assert labeled.filter(pl.col("work_id") == "RECENT_OPEN").height == 0
    assert dataset["score"].filter(pl.col("work_id") == "RECENT_OPEN").height == 1


def test_prior_count_features_have_no_lookahead():
    rows = [
        {"work_id": "FIRST", "implementing_agency": "AGENCY_A", "mp_name": "MP1", "sanction_date": date(2024, 1, 1)},
        {"work_id": "SECOND", "implementing_agency": "AGENCY_A", "mp_name": "MP1", "sanction_date": date(2024, 2, 1)},
        {"work_id": "THIRD", "implementing_agency": "AGENCY_A", "mp_name": "MP1", "sanction_date": date(2024, 3, 1)},
    ]
    works = make_works(rows)
    featured = _add_features(works)
    first = featured.filter(pl.col("work_id") == "FIRST")
    second = featured.filter(pl.col("work_id") == "SECOND")
    third = featured.filter(pl.col("work_id") == "THIRD")
    assert first["agency_prior_count"][0] == 0
    assert second["agency_prior_count"][0] == 1
    assert third["agency_prior_count"][0] == 2
