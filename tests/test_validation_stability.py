from datetime import date

import polars as pl

from parakh.validation.stability import BOOTSTRAP_RETENTION_CEILING, bootstrap_stability

_SCHEMA = {
    "work_id": pl.Utf8,
    "house": pl.Utf8,
    "term": pl.Utf8,
    "state": pl.Utf8,
    "district_raw": pl.Utf8,
    "implementing_agency": pl.Utf8,
    "mp_name": pl.Utf8,
    "constituency": pl.Utf8,
    "elected_or_nominated": pl.Utf8,
    "category_broad": pl.Utf8,
    "category": pl.Utf8,
    "description": pl.Utf8,
    "description_corrupted": pl.Boolean,
    "recommended_date": pl.Date,
    "recommended_amount": pl.Float64,
    "sanction_date": pl.Date,
    "sanction_amount": pl.Float64,
    "work_status": pl.Utf8,
    "completion_date": pl.Date,
    "amount_disbursed_at_completion": pl.Float64,
    "has_image_evidence": pl.Boolean,
    "financial_year": pl.Utf8,
    "quantity": pl.Float64,
    "quantity_unit": pl.Utf8,
}


def _row(i: int, **overrides) -> dict:
    base = {
        "work_id": f"WS/MP1/2024-2025/{i}",
        "house": "Lok Sabha",
        "term": "18th",
        "state": "Bihar",
        "district_raw": "PATNA",
        "implementing_agency": "AGENCY_A",
        "mp_name": "MP_ONE",
        "constituency": "PATNA",
        "elected_or_nominated": "Elected",
        "category_broad": "Normal",
        "category": "Street lights",
        "description": f"Streetlight {i}",
        "description_corrupted": False,
        "recommended_date": date(2024, 1, 1),
        "recommended_amount": 500_000.0,
        "sanction_date": date(2024, 2, 1),
        "sanction_amount": 500_000.0,
        "work_status": "Sanction",
        "completion_date": None,
        "amount_disbursed_at_completion": None,
        "has_image_evidence": True,
        "financial_year": "2024-2025",
        "quantity": None,
        "quantity_unit": None,
    }
    base.update(overrides)
    return base


def test_bootstrap_stability_returns_all_six_detectors_with_valid_ranges():
    works = pl.DataFrame([_row(i) for i in range(60)], schema=_SCHEMA)
    expenditure = pl.DataFrame(schema={"work_id": pl.Utf8, "amount": pl.Float64})

    result = bootstrap_stability(works, expenditure, n_bootstrap=2, seed=1)

    assert result["_retention_ceiling"] == BOOTSTRAP_RETENTION_CEILING
    for detector in ["B1", "B2", "B3", "B4", "B6", "B7"]:
        assert detector in result
        r = result[detector]
        assert 0.0 <= r["mean_jaccard_vs_baseline"] <= 1.0
        assert 0.0 <= r["min_jaccard_vs_baseline"] <= r["mean_jaccard_vs_baseline"] <= r["max_jaccard_vs_baseline"] <= 1.0
        assert r["n_bootstrap"] == 2


def test_bootstrap_retention_ceiling_is_one_minus_one_over_e():
    assert 0.63 < BOOTSTRAP_RETENTION_CEILING < 0.64
