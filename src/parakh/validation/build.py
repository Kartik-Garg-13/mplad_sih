"""Computes all four plan §07 validation methods and writes their
results as tables into the already-built parakh.duckdb — the fifth
method (the stall model's time-split PR-AUC/calibration) is already
persisted by database.py as model_metrics/feature_importances, so it
isn't recomputed here.

Deliberately a second pass over an existing database.py-built file
(opened read-write, not the read-only mode the API uses), not folded
into build_database() itself: validation is a report ABOUT the
detectors that database.py just built, and keeping it a separate,
independently-rerunnable step means re-validating never requires
rerunning the full detector/graph/model pipeline first.

    python -m parakh.database          # build everything
    python -m parakh.validation.build  # then validate it
"""

from __future__ import annotations

import duckdb
import polars as pl

from parakh.config import PROCESSED_DIR
from parakh.database import DB_PATH
from parakh.validation.adjudication import adjudication_result
from parakh.validation.evaluate import evaluate_synthetic_injection
from parakh.validation.known_cases import known_case_backtest_result
from parakh.validation.stability import bootstrap_stability


def build_validation_tables() -> None:
    works = pl.read_parquet(PROCESSED_DIR / "works.parquet")
    expenditure = pl.read_parquet(PROCESSED_DIR / "expenditure.parquet")

    synthetic = evaluate_synthetic_injection(works, expenditure)
    stability = bootstrap_stability(works, expenditure)
    known_cases = known_case_backtest_result()
    adjudication = adjudication_result()

    synthetic_per_type = pl.DataFrame(synthetic["per_type"])
    synthetic_at_k = pl.DataFrame(synthetic["at_k"])
    stability_rows = pl.DataFrame(
        [{"detector": k, **v} for k, v in stability.items() if not k.startswith("_")]
    )
    known_case_rows = pl.DataFrame(known_cases["cases"])
    adjudication_rows = pl.DataFrame(adjudication["clusters"])

    con = duckdb.connect(str(DB_PATH))
    try:
        con.register("synthetic_per_type_df", synthetic_per_type)
        con.register("synthetic_at_k_df", synthetic_at_k)
        con.register("stability_df", stability_rows)
        con.register("known_cases_df", known_case_rows)
        con.register("adjudication_clusters_df", adjudication_rows)

        con.execute("CREATE OR REPLACE TABLE validation_synthetic_per_type AS SELECT * FROM synthetic_per_type_df")
        con.execute("CREATE OR REPLACE TABLE validation_synthetic_at_k AS SELECT * FROM synthetic_at_k_df")
        con.execute("CREATE OR REPLACE TABLE validation_stability AS SELECT * FROM stability_df")
        con.execute("CREATE OR REPLACE TABLE validation_known_cases AS SELECT * FROM known_cases_df")
        con.execute("CREATE OR REPLACE TABLE validation_adjudication_clusters AS SELECT * FROM adjudication_clusters_df")

        print(f"synthetic injection: {synthetic['n_injected_total']} injected, per-type recall in validation_synthetic_per_type")
        print(f"stability: {len(stability_rows)} detectors checked, see validation_stability")
        print(f"known cases: {known_cases['n_matched']}/{known_cases['n_cases_checked']} matched")
        print(f"adjudication: {adjudication['conclusion']}")
        print(f"-> {DB_PATH}")
    finally:
        con.close()


if __name__ == "__main__":
    build_validation_tables()
