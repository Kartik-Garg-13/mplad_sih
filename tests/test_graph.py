import polars as pl

from parakh.graph import (
    build_agency_vendor_edges,
    build_mp_agency_edges,
    compute_agency_metrics,
    compute_communities,
)

_WORKS_SCHEMA = {
    "sanction_amount": pl.Float64,
    "implementing_agency": pl.Utf8,
    "mp_name": pl.Utf8,
    "state": pl.Utf8,
}


def make_works(rows: list[dict]) -> pl.DataFrame:
    return pl.DataFrame(rows, schema=_WORKS_SCHEMA)


def test_build_mp_agency_edges_aggregates_correctly():
    works = make_works(
        [
            {"sanction_amount": 100_000.0, "implementing_agency": "AGENCY_A", "mp_name": "MP1", "state": "Bihar"},
            {"sanction_amount": 200_000.0, "implementing_agency": "AGENCY_A", "mp_name": "MP1", "state": "Bihar"},
            {"sanction_amount": 50_000.0, "implementing_agency": "AGENCY_B", "mp_name": "MP1", "state": "Bihar"},
        ]
    )
    edges = build_mp_agency_edges(works)
    a_edge = edges.filter((pl.col("mp_name") == "MP1") & (pl.col("implementing_agency") == "AGENCY_A"))
    assert a_edge["n_works"][0] == 2
    assert a_edge["total_value"][0] == 300_000.0


def test_build_agency_vendor_edges_ignores_missing_vendor():
    exp = pl.DataFrame(
        {
            "implementing_agency": ["AGENCY_A", "AGENCY_A", "AGENCY_A"],
            "vendor_name": ["Vendor X", None, ""],
            "amount": [1000.0, 2000.0, 3000.0],
        }
    )
    edges = build_agency_vendor_edges(exp)
    assert edges.height == 1
    assert edges["n_payments"][0] == 1


def test_compute_communities_separates_disconnected_clusters():
    works = make_works(
        [
            {"sanction_amount": 100_000.0, "implementing_agency": "AGENCY_A", "mp_name": "MP1", "state": "Bihar"},
            {"sanction_amount": 100_000.0, "implementing_agency": "AGENCY_A", "mp_name": "MP2", "state": "Bihar"},
            {"sanction_amount": 100_000.0, "implementing_agency": "AGENCY_Z", "mp_name": "MP9", "state": "Kerala"},
            {"sanction_amount": 100_000.0, "implementing_agency": "AGENCY_Z", "mp_name": "MP8", "state": "Kerala"},
        ]
    )
    edges = build_mp_agency_edges(works)
    communities = compute_communities(edges)
    a_community = communities.filter(pl.col("label") == "AGENCY_A")["community"][0]
    z_community = communities.filter(pl.col("label") == "AGENCY_Z")["community"][0]
    assert a_community != z_community
    # Nodes sharing an edge land in the same community.
    mp1_community = communities.filter(pl.col("label") == "MP1")["community"][0]
    assert mp1_community == a_community


def test_thin_file_agency_flagged():
    # 30 "normal" agencies at typical value-per-work, plus one agency
    # with 2 works at a much higher value-per-work.
    rows = []
    for a in range(30):
        rows.append({"sanction_amount": 100_000.0, "implementing_agency": f"NORMAL_{a}", "mp_name": "MPx", "state": "Bihar"})
    rows.append({"sanction_amount": 5_000_000.0, "implementing_agency": "THIN_FILE", "mp_name": "MPy", "state": "Bihar"})
    rows.append({"sanction_amount": 5_000_000.0, "implementing_agency": "THIN_FILE", "mp_name": "MPz", "state": "Bihar"})
    works = make_works(rows)
    metrics = compute_agency_metrics(works)
    thin = metrics.filter(pl.col("implementing_agency") == "THIN_FILE")
    assert thin["is_thin_file"][0] is True
    normal = metrics.filter(pl.col("implementing_agency") == "NORMAL_0")
    assert normal["is_thin_file"][0] is False


def test_thin_file_not_flagged_when_many_works():
    # Same high value-per-work, but too many works to be "thin file".
    rows = [{"sanction_amount": 100_000.0, "implementing_agency": f"NORMAL_{a}", "mp_name": "MPx", "state": "Bihar"} for a in range(30)]
    rows += [
        {"sanction_amount": 5_000_000.0, "implementing_agency": "BIG_BUT_HIGH_VALUE", "mp_name": "MPy", "state": "Bihar"}
        for _ in range(10)
    ]
    works = make_works(rows)
    metrics = compute_agency_metrics(works)
    big = metrics.filter(pl.col("implementing_agency") == "BIG_BUT_HIGH_VALUE")
    assert big["is_thin_file"][0] is False


def test_cross_state_agency_flagged():
    works = make_works(
        [
            {"sanction_amount": 100_000.0, "implementing_agency": "WEIRD_AGENCY", "mp_name": "MP1", "state": "Bihar"},
            {"sanction_amount": 100_000.0, "implementing_agency": "WEIRD_AGENCY", "mp_name": "MP2", "state": "Kerala"},
            {"sanction_amount": 100_000.0, "implementing_agency": "NORMAL_AGENCY", "mp_name": "MP3", "state": "Bihar"},
        ]
    )
    metrics = compute_agency_metrics(works)
    assert metrics.filter(pl.col("implementing_agency") == "WEIRD_AGENCY")["is_cross_state"][0] is True
    assert metrics.filter(pl.col("implementing_agency") == "NORMAL_AGENCY")["is_cross_state"][0] is False
