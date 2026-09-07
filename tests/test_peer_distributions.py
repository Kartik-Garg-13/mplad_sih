import statistics
from datetime import date, timedelta

import polars as pl

from parakh.peer_distributions import build_peer_distributions, group_key
from parakh.peer_stats import DEFAULT_MIN_PEER_GROUP

_WORKS_SCHEMA = {
    "work_id": pl.Utf8,
    "category": pl.Utf8,
    "state": pl.Utf8,
    "financial_year": pl.Utf8,
    "sanction_amount": pl.Float64,
    "sanction_date": pl.Date,
    "completion_date": pl.Date,
}


def _work(i: int, **overrides) -> dict:
    base = {
        "work_id": f"WS/MP1/2024-2025/{i}",
        "category": "Street lights",
        "state": "Bihar",
        "financial_year": "2024-2025",
        "sanction_amount": 100_000.0,
        "sanction_date": date(2024, 1, 1),
        "completion_date": date(2024, 2, 1),
    }
    base.update(overrides)
    return base


def _frame(rows: list[dict]) -> pl.DataFrame:
    return pl.DataFrame(rows, schema=_WORKS_SCHEMA)


def test_group_below_min_n_is_excluded():
    works = _frame([_work(i) for i in range(DEFAULT_MIN_PEER_GROUP - 1)])
    dist = build_peer_distributions(works)
    assert dist.filter(pl.col("detector") == "B1").height == 0


def test_eligible_group_produces_a_histogram_whose_counts_sum_to_n():
    n = DEFAULT_MIN_PEER_GROUP + 5
    amounts = [50_000.0 + i * 10_000.0 for i in range(n)]  # a real spread, not one repeated value
    works = _frame([_work(i, sanction_amount=amounts[i]) for i in range(n)])
    dist = build_peer_distributions(works)
    row = dist.filter(pl.col("detector") == "B1").row(0, named=True)

    assert row["n"] == n
    assert sum(row["bucket_counts"]) == n
    assert row["median"] == statistics.median(amounts)
    assert row["group_key"] == group_key("Street lights", "Bihar", "2024-2025")


def test_a_flagged_works_own_value_lands_in_the_correct_bucket():
    """The check the plan itself calls out: a chart's marked position must
    match the amount a flag's own evidence sentence states. This proves the
    bucket edges bracket the real min/max, so any value inside the group's
    range resolves to a real bucket index — the same arithmetic the API
    endpoint (see api/main.py's peers endpoint) uses to place a work's own
    marker on the histogram."""
    n = DEFAULT_MIN_PEER_GROUP
    amounts = [float(i * 1000) for i in range(n)]  # 0, 1000, ..., 29000
    works = _frame([_work(i, sanction_amount=amounts[i]) for i in range(n)])
    dist = build_peer_distributions(works)
    row = dist.filter(pl.col("detector") == "B1").row(0, named=True)

    edges = row["bucket_edges"]
    assert edges[0] == min(amounts)
    assert edges[-1] == max(amounts)

    # The lowest value must resolve into the first bucket, the highest into
    # the last — the two boundary cases a bucketing scheme most easily gets
    # wrong (an off-by-one at either edge leaves a real data point unplaced).
    lo_bucket = next(i for i in range(len(edges) - 1) if edges[i] <= min(amounts) <= edges[i + 1])
    hi_bucket = next(i for i in range(len(edges) - 1) if edges[i] <= max(amounts) <= edges[i + 1])
    assert lo_bucket == 0
    assert hi_bucket == len(row["bucket_counts"]) - 1


def test_degenerate_group_where_every_peer_shares_one_value_does_not_crash():
    n = DEFAULT_MIN_PEER_GROUP
    works = _frame([_work(i, sanction_amount=250_000.0) for i in range(n)])
    dist = build_peer_distributions(works)
    row = dist.filter(pl.col("detector") == "B1").row(0, named=True)

    assert row["n"] == n
    assert row["median"] == 250_000.0
    assert sum(row["bucket_counts"]) == n


def test_b3_only_uses_completed_works_with_real_category_and_state():
    n = DEFAULT_MIN_PEER_GROUP
    completed = [
        _work(i, sanction_date=date(2024, 1, 1), completion_date=date(2024, 1, 1) + timedelta(days=i + 10))
        for i in range(n)
    ]
    still_open = [_work(1000 + i, completion_date=None) for i in range(5)]
    no_category = [_work(2000 + i, category=None, completion_date=date(2024, 3, 1)) for i in range(5)]
    works = _frame(completed + still_open + no_category)

    dist = build_peer_distributions(works)
    b3 = dist.filter(pl.col("detector") == "B3")
    assert b3.height == 1
    assert b3.row(0, named=True)["n"] == n  # open and no-category rows excluded, not counted


def test_group_key_uses_a_delimiter_that_cannot_appear_in_real_text():
    key = group_key("Category with | a pipe", "State-name", "2024-2025")
    assert key.count("\x1f") == 2
    # A naive "|" join would be ambiguous here; the real separator is not.
    assert key != "Category with | a pipe|State-name|2024-2025"
