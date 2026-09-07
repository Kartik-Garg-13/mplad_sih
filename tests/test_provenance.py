from datetime import date

import polars as pl

from parakh.provenance import SOURCE_URL, build_provenance_record

_WORKS = pl.DataFrame(
    {
        "work_id": ["WS/MP1/2024-2025/1", "WS/MP1/2024-2025/2", "WS/MP2/2025-2026/1"],
        "state": ["Bihar", "Bihar", "Kerala"],
        "mp_name": ["A", "A", "B"],
        "implementing_agency": ["Agency1", "Agency1", "Agency2"],
        "house": ["Lok Sabha", "Lok Sabha", "Rajya Sabha"],
        "term": ["18th", "18th", "18th"],
        "financial_year": ["2024-2025", "2024-2025", "2025-2026"],
        "quantity": [100.0, None, None],
        "has_image_evidence": [True, False, True],
        "description_corrupted": [False, False, True],
    }
)
_EXPENDITURE = pl.DataFrame({"work_id": ["WS/MP1/2024-2025/1"], "amount": [1000.0]})
_ALLOCATED = pl.DataFrame({"mp_name": ["A", "B"], "allocated_amount": [1.0, 2.0]})


def test_build_provenance_record_counts():
    record = build_provenance_record(_WORKS, _EXPENDITURE, _ALLOCATED)

    assert record["n_works"] == 3
    assert record["n_expenditure_records"] == 1
    assert record["n_allocated_records"] == 2
    assert record["n_states"] == 2
    assert record["n_mps"] == 2
    assert record["n_agencies"] == 2


def test_build_provenance_record_coverage_shares():
    record = build_provenance_record(_WORKS, _EXPENDITURE, _ALLOCATED)

    assert record["quantity_coverage"] == round(1 / 3, 4)
    assert record["image_evidence_coverage"] == round(2 / 3, 4)
    assert record["description_corruption_rate"] == round(1 / 3, 4)


def test_build_provenance_record_static_fields():
    record = build_provenance_record(_WORKS, _EXPENDITURE, _ALLOCATED)

    assert record["source_url"] == SOURCE_URL
    assert record["snapshot_date"] == date.today().isoformat()


def test_houses_covered_is_derived_from_the_actual_works_present():
    """Not a hardcoded string: it names exactly the house/term pairs found
    in `works`, so a dataset upload (or removal) can never leave this
    stale — the exact failure mode a fixed string has once a batch can add
    a third source or replace one of the original two."""
    record = build_provenance_record(_WORKS, _EXPENDITURE, _ALLOCATED)
    assert record["houses_covered"] == "Lok Sabha (18th term), Rajya Sabha (18th term)"


def test_houses_covered_names_an_uploaded_batch_with_no_term_by_house_alone():
    works = _WORKS.with_columns(
        pl.when(pl.col("state") == "Kerala").then(pl.lit("Pilot District")).otherwise(pl.col("house")).alias("house"),
        pl.when(pl.col("state") == "Kerala").then(pl.lit("—")).otherwise(pl.col("term")).alias("term"),
    )
    record = build_provenance_record(works, _EXPENDITURE, _ALLOCATED)
    assert record["houses_covered"] == "Lok Sabha (18th term), Pilot District"


def test_financial_year_range_reflects_the_actual_data():
    record = build_provenance_record(_WORKS, _EXPENDITURE, _ALLOCATED)
    assert record["financial_year_earliest"] == "2024-2025"
    assert record["financial_year_latest"] == "2025-2026"


def test_build_provenance_record_empty_works():
    empty = _WORKS.clear()
    record = build_provenance_record(empty, _EXPENDITURE.clear(), _ALLOCATED.clear())

    assert record["n_works"] == 0
    assert record["quantity_coverage"] == 0.0
    assert record["image_evidence_coverage"] == 0.0
    assert record["description_corruption_rate"] == 0.0
    assert record["houses_covered"] == "no sources loaded"
    assert record["financial_year_earliest"] is None
    assert record["financial_year_latest"] is None
