"""Parquet + detector output -> one DuckDB file, read-only after this.

Plan §02: nothing downstream of this script ever computes a detector
live. The API only reads `data/processed/parakh.duckdb`; a full
refresh is `python -m parakh.database`, which reruns every detector
against the current Parquet snapshot and rewrites the file from
scratch — a few seconds, not a service.
"""

from __future__ import annotations

import os

import duckdb
import polars as pl

from parakh.config import PROCESSED_DIR
from parakh.constituency import compute_constituency_scorecard
from parakh.detectors import run_all
from parakh.graph import build_agency_vendor_edges, build_mp_agency_edges, compute_agency_metrics, compute_communities
from parakh.peer_distributions import build_peer_distributions
from parakh.provenance import build_provenance_record
from parakh.stall_model import score_at_risk_works, train_and_evaluate

DB_PATH = PROCESSED_DIR / "parakh.duckdb"
# Same directory as DB_PATH — os.replace() below is only atomic within one
# filesystem, and a temp-directory build could land on a different one.
_TMP_DB_PATH = PROCESSED_DIR / "parakh.duckdb.building"


def build_database() -> None:
    works = pl.read_parquet(PROCESSED_DIR / "works.parquet")
    expenditure = pl.read_parquet(PROCESSED_DIR / "expenditure.parquet")
    allocated = pl.read_parquet(PROCESSED_DIR / "allocated.parquet")
    calamity = pl.read_parquet(PROCESSED_DIR / "calamity.parquet")
    flags = run_all(works, expenditure)

    mp_agency_edges = build_mp_agency_edges(works)
    agency_vendor_edges = build_agency_vendor_edges(expenditure)
    agency_metrics = compute_agency_metrics(works).drop("states")
    communities = compute_communities(mp_agency_edges)

    stall_result = train_and_evaluate(works)
    at_risk = score_at_risk_works(stall_result["model"], stall_result["score_set"]).join(
        works.select(["work_id", "state", "district_raw", "implementing_agency", "mp_name", "category", "description", "sanction_amount"]),
        on="work_id",
        how="left",
    )
    model_metrics = pl.DataFrame(
        {
            "n_train": [stall_result["n_train"]],
            "n_test": [stall_result["n_test"]],
            "positive_rate_train": [stall_result["positive_rate_train"]],
            "positive_rate_test": [stall_result["positive_rate_test"]],
            "pr_auc": [stall_result["pr_auc"]],
            "roc_auc": [stall_result["roc_auc"]],
            "calibration_mean_predicted": [stall_result["calibration"]["mean_predicted"]],
            "calibration_fraction_positive": [stall_result["calibration"]["fraction_positive"]],
        }
    )
    feature_importances = pl.DataFrame(
        {
            "feature": list(stall_result["feature_importances"].keys()),
            "importance": list(stall_result["feature_importances"].values()),
        }
    ).sort("importance", descending=True)

    constituency_scorecard = compute_constituency_scorecard(works, expenditure, allocated)
    peer_distributions = build_peer_distributions(works)
    provenance = pl.DataFrame([build_provenance_record(works, expenditure, allocated)])

    # Built to a temp file and swapped in with os.replace() at the very end
    # (atomic on both POSIX and Windows within one filesystem) — building
    # straight over DB_PATH means unlinking it first, so any failure between
    # that unlink and a successful close (bad data reaching a detector,
    # a training error, the process being killed) leaves the API with no
    # database at all and no way back short of a manual CLI rebuild. The old
    # file now stays in place, correct and serving, until a new one is fully
    # built and verified.
    if _TMP_DB_PATH.exists():
        _TMP_DB_PATH.unlink()
    con = duckdb.connect(str(_TMP_DB_PATH))
    try:
        con.register("works_df", works)
        con.register("expenditure_df", expenditure)
        con.register("allocated_df", allocated)
        con.register("calamity_df", calamity)
        con.register("flags_df", flags)
        con.register("mp_agency_edges_df", mp_agency_edges)
        con.register("agency_vendor_edges_df", agency_vendor_edges)
        con.register("agency_metrics_df", agency_metrics)
        con.register("communities_df", communities)
        con.register("at_risk_df", at_risk)
        con.register("model_metrics_df", model_metrics)
        con.register("feature_importances_df", feature_importances)
        con.register("constituency_scorecard_df", constituency_scorecard)
        con.register("peer_distributions_df", peer_distributions)
        con.register("provenance_df", provenance)

        con.execute("CREATE TABLE works AS SELECT * FROM works_df")
        con.execute("CREATE TABLE expenditure AS SELECT * FROM expenditure_df")
        con.execute("CREATE TABLE allocated AS SELECT * FROM allocated_df")
        con.execute("CREATE TABLE calamity AS SELECT * FROM calamity_df")
        con.execute("CREATE TABLE flags AS SELECT * FROM flags_df")
        con.execute("CREATE TABLE mp_agency_edges AS SELECT * FROM mp_agency_edges_df")
        con.execute("CREATE TABLE agency_vendor_edges AS SELECT * FROM agency_vendor_edges_df")
        con.execute("CREATE TABLE agency_metrics AS SELECT * FROM agency_metrics_df")
        con.execute("CREATE TABLE communities AS SELECT * FROM communities_df")
        con.execute("CREATE TABLE at_risk AS SELECT * FROM at_risk_df")
        con.execute("CREATE TABLE model_metrics AS SELECT * FROM model_metrics_df")
        con.execute("CREATE TABLE feature_importances AS SELECT * FROM feature_importances_df")
        con.execute("CREATE TABLE constituency_scorecard AS SELECT * FROM constituency_scorecard_df")
        con.execute("CREATE TABLE peer_distributions AS SELECT * FROM peer_distributions_df")
        con.execute("CREATE TABLE provenance AS SELECT * FROM provenance_df")

        con.execute(
            """
            CREATE TABLE work_flag_summary AS
            SELECT
                work_id,
                count(*) AS n_flags,
                list(DISTINCT detector) AS detectors,
                bool_or(tier = 'A') AS has_tier_a,
                bool_or(tier = 'B') AS has_tier_b
            FROM flags
            GROUP BY work_id
            """
        )

        con.execute("CREATE INDEX idx_flags_work_id ON flags(work_id)")
        con.execute("CREATE INDEX idx_flags_detector ON flags(detector)")
        con.execute("CREATE INDEX idx_works_work_id ON works(work_id)")
        con.execute("CREATE INDEX idx_summary_work_id ON work_flag_summary(work_id)")
        con.execute("CREATE INDEX idx_agency_metrics_name ON agency_metrics(implementing_agency)")
        con.execute("CREATE INDEX idx_mp_agency_edges_agency ON mp_agency_edges(implementing_agency)")
        con.execute("CREATE INDEX idx_agency_vendor_edges_agency ON agency_vendor_edges(implementing_agency)")
        con.execute("CREATE INDEX idx_at_risk_work_id ON at_risk(work_id)")
        con.execute("CREATE INDEX idx_scorecard_constituency ON constituency_scorecard(state, constituency)")
        con.execute("CREATE INDEX idx_peer_distributions_lookup ON peer_distributions(detector, group_key)")

        n_works = con.execute("SELECT count(*) FROM works").fetchone()[0]
        n_flags = con.execute("SELECT count(*) FROM flags").fetchone()[0]
        n_flagged = con.execute("SELECT count(*) FROM work_flag_summary").fetchone()[0]
        n_agencies = con.execute("SELECT count(*) FROM agency_metrics").fetchone()[0]
        n_thin = con.execute("SELECT count(*) FROM agency_metrics WHERE is_thin_file").fetchone()[0]
        n_cross = con.execute("SELECT count(*) FROM agency_metrics WHERE is_cross_state").fetchone()[0]
        print(f"works:          {n_works:>8,}")
        print(f"flags:          {n_flags:>8,}")
        print(f"flagged works:  {n_flagged:>8,} ({n_flagged / n_works:.1%})")
        print(f"agencies:       {n_agencies:>8,}  (thin-file {n_thin}, cross-state {n_cross})")
        print(
            f"stall model:    PR-AUC {stall_result['pr_auc']:.3f} / ROC-AUC {stall_result['roc_auc']:.3f}"
            f"  ({stall_result['n_train']:,} train / {stall_result['n_test']:,} test)"
        )
        print(f"at-risk works:  {at_risk.height:>8,}")
        print(f"constituencies: {constituency_scorecard.height:>8,}")
        print(f"peer groups:    {peer_distributions.height:>8,}  (B1/B3 histograms)")
    except Exception:
        con.close()
        _TMP_DB_PATH.unlink(missing_ok=True)
        raise
    else:
        con.close()
        os.replace(_TMP_DB_PATH, DB_PATH)
        print(f"-> {DB_PATH}")


if __name__ == "__main__":
    build_database()
