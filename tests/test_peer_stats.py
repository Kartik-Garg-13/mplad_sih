import polars as pl

from parakh.peer_stats import add_robust_z


def _uniform_group(group: str, n: int, value: float) -> list[dict]:
    return [{"grp": group, "v": value} for _ in range(n)]


def test_abstains_below_min_n():
    rows = _uniform_group("A", 10, 100.0)  # below default min_n=30
    df = pl.DataFrame(rows)
    out = add_robust_z(df, "v", ["grp"], min_n=30)
    assert out["robust_z"].null_count() == 10


def test_computes_z_for_large_enough_group():
    # 30 peers at 100, one outlier at 400.
    rows = _uniform_group("A", 30, 100.0) + [{"grp": "A", "v": 400.0}]
    df = pl.DataFrame(rows)
    out = add_robust_z(df, "v", ["grp"], min_n=30)
    outlier = out.filter(pl.col("v") == 400.0)
    assert outlier["peer_n"][0] == 31
    assert outlier["peer_median"][0] == 100.0
    assert outlier["robust_z"][0] > 3.0  # clearly an outlier


def test_zero_mad_matching_value_scores_zero():
    rows = _uniform_group("A", 35, 50.0)
    df = pl.DataFrame(rows)
    out = add_robust_z(df, "v", ["grp"], min_n=30)
    assert (out["robust_z"] == 0.0).all()


def test_zero_mad_but_real_iqr_spread_gets_a_proportional_z_not_a_flat_sentinel():
    """A bare majority (not the bulk) shares the median, so MAD is zero,
    but the tails carry real spread (nonzero IQR) — this must produce a
    z-score whose magnitude actually reflects how far out the value is,
    not a flat 999 regardless of how close the value is to the median.
    This is the exact shape that produced self-refuting B1 evidence in
    the real corpus ("is 1.0x the peer median" on a >3.5-sigma flag).
    """
    # 16 peers at 50 (a plain majority, MAD=0), then a spread tail so
    # Q25/Q75 differ: a near-median value should NOT score as an extreme
    # outlier, while a genuinely distant one should.
    rows = (
        _uniform_group("A", 16, 50.0)
        + [{"grp": "A", "v": v} for v in [10.0, 20.0, 30.0, 40.0, 60.0, 70.0, 80.0, 90.0, 100.0, 110.0, 120.0, 130.0, 140.0, 150.0]]
    )
    df = pl.DataFrame(rows)
    out = add_robust_z(df, "v", ["grp"], min_n=30)
    assert (out["peer_mad"] == 0).all()

    near_median = out.filter(pl.col("v") == 60.0)["robust_z"][0]
    far_outlier = out.filter(pl.col("v") == 150.0)["robust_z"][0]
    assert near_median is not None and abs(near_median) < 3.5, (
        "a value barely off the median must not score as an extreme outlier "
        "just because MAD happened to be zero"
    )
    assert far_outlier is not None and far_outlier != 999.0, (
        "the IQR fallback should produce a real proportional z, not the flat "
        "degenerate-case sentinel"
    )
    assert far_outlier > near_median


def test_fully_degenerate_group_abstains_on_a_small_deviation():
    """MAD and IQR both zero (>=75% share one exact value) and the
    differing value is close to the median in plain terms — there is no
    spread estimate to judge magnitude against, so this must abstain
    (null) rather than report an arbitrary extreme z, the bug confirmed
    in the real corpus (e.g. sanction amount reported as "1.0x the peer
    median" while flagged as a >3.5-sigma cost outlier).
    """
    rows = _uniform_group("A", 34, 50.0) + [{"grp": "A", "v": 52.0}]  # ~1.04x the median
    df = pl.DataFrame(rows)
    out = add_robust_z(df, "v", ["grp"], min_n=30)
    odd_one = out.filter(pl.col("v") == 52.0)
    assert odd_one["peer_mad"][0] == 0
    assert odd_one["robust_z"][0] is None


def test_fully_degenerate_group_still_flags_a_genuinely_large_deviation():
    rows = _uniform_group("A", 34, 50.0) + [{"grp": "A", "v": 999_999.0}]
    df = pl.DataFrame(rows)
    out = add_robust_z(df, "v", ["grp"], min_n=30)
    odd_one = out.filter(pl.col("v") == 999_999.0)
    assert odd_one["robust_z"][0] == 999.0
    assert odd_one["robust_z"][0] is not None


def test_groups_do_not_leak_into_each_other():
    rows = _uniform_group("A", 40, 10.0) + _uniform_group("B", 40, 1000.0)
    df = pl.DataFrame(rows)
    out = add_robust_z(df, "v", ["grp"], min_n=30)
    a_medians = out.filter(pl.col("grp") == "A")["peer_median"].unique().to_list()
    b_medians = out.filter(pl.col("grp") == "B")["peer_median"].unique().to_list()
    assert a_medians == [10.0]
    assert b_medians == [1000.0]


def test_multi_column_grouping():
    rows = (
        [{"state": "Bihar", "cat": "Road", "v": 100.0} for _ in range(30)]
        + [{"state": "Bihar", "cat": "Light", "v": 5.0} for _ in range(30)]
    )
    df = pl.DataFrame(rows)
    out = add_robust_z(df, "v", ["state", "cat"], min_n=30)
    road_median = out.filter(pl.col("cat") == "Road")["peer_median"].unique().to_list()
    light_median = out.filter(pl.col("cat") == "Light")["peer_median"].unique().to_list()
    assert road_median == [100.0]
    assert light_median == [5.0]


def test_a_value_close_to_its_peer_median_abstains_however_tight_the_group():
    """The materiality floor (plan §08 rule 2 — a flag has to be evidence).

    A peer group clustered on one round figure collapses the spread
    estimate, and an ordinary value then scores as an extreme outlier. On
    the real corpus this produced 73 flags whose own evidence sentence
    read "is 1.0x the peer median" while calling the work an outlier —
    the tool contradicting itself in the sentence a reviewer must trust.
    """
    # 40 peers on an exact round figure, plus two at 4% either side: a
    # near-zero spread estimate, but no material difference in rupees.
    rows = _uniform_group("A", 40, 500_000.0) + [
        {"grp": "A", "v": 520_000.0},
        {"grp": "A", "v": 480_000.0},
    ]
    out = add_robust_z(pl.DataFrame(rows), "v", ["grp"], min_n=30)

    for value in (520_000.0, 480_000.0):
        z = out.filter(pl.col("v") == value)["robust_z"][0]
        assert z is None, f"{value} is within 10% of the median and must abstain, got z={z}"


def test_the_floor_does_not_suppress_a_genuine_outlier():
    rows = _uniform_group("A", 40, 500_000.0) + [{"grp": "A", "v": 5_000_000.0}]
    out = add_robust_z(pl.DataFrame(rows), "v", ["grp"], min_n=30)
    z = out.filter(pl.col("v") == 5_000_000.0)["robust_z"][0]
    assert z is not None and abs(z) > 3.5


def test_the_floor_is_relative_not_absolute():
    """10% of a small median is a small number of rupees, and 10% of a
    large one is a large number — the gate has to scale with the group."""
    small = _uniform_group("S", 40, 1_000.0) + [{"grp": "S", "v": 1_050.0}]
    out = add_robust_z(pl.DataFrame(small), "v", ["grp"], min_n=30)
    assert out.filter(pl.col("v") == 1_050.0)["robust_z"][0] is None

    large = _uniform_group("L", 40, 10_000_000.0) + [{"grp": "L", "v": 10_500_000.0}]
    out = add_robust_z(pl.DataFrame(large), "v", ["grp"], min_n=30)
    assert out.filter(pl.col("v") == 10_500_000.0)["robust_z"][0] is None
