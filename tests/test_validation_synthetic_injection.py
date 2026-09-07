from datetime import date

import polars as pl

from parakh.validation.synthetic_injection import (
    _find_concentration_target,
    inject_agency_concentration,
    inject_duplicate_record,
    inject_inflated_cost,
    inject_phantom_completion,
    inject_split_work,
)

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

_DEFAULT_ROW = {
    "house": "Lok Sabha",
    "term": "18th",
    "state": "Bihar",
    "district_raw": "PATNA",
    "implementing_agency": "DISTRICT PLANNING OFFICER PATNA_IDA",
    "mp_name": "TEST MP",
    "constituency": "PATNA",
    "elected_or_nominated": "Elected",
    "category_broad": "Normal",
    "category": "Street lights",
    "description": "Installation of solar street light",
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


def make_works(rows: list[dict]) -> pl.DataFrame:
    full_rows = [{**_DEFAULT_ROW, **r} for r in rows]
    return pl.DataFrame(full_rows, schema=_SCHEMA)


def test_inject_inflated_cost_multiplies_and_ids_are_unique():
    works = make_works([{"work_id": f"WS/MP1/2024-2025/{i}"} for i in range(10)])
    injected, ids = inject_inflated_cost(works, seed=1, n=5)

    assert injected.height == 5
    assert len(set(ids)) == 5
    assert set(injected["work_id"].to_list()) == set(ids)
    assert all(a > 500_000.0 * 9 for a in injected["sanction_amount"].to_list())
    assert set(injected["category"].to_list()) == {"Street lights"}


def test_inject_split_work_creates_clusters_with_similar_but_distinct_descriptions():
    works = make_works(
        [
            {"work_id": f"WS/MP1/2024-2025/{i}", "description": f"Installation of solar street light type {i}"}
            for i in range(10)
        ]
    )
    injected, ids = inject_split_work(works, seed=2, n_clusters=2, cluster_size=3)

    assert injected.height == 6
    assert len(set(ids)) == 6
    descriptions = injected["description"].to_list()
    assert len(set(descriptions)) == 6  # every member's description is distinct
    assert all("Installation of solar street light" in d for d in descriptions)
    assert set(injected["work_status"].to_list()) == {"Sanction"}
    assert injected["completion_date"].null_count() == 6


def test_inject_duplicate_record_reuses_real_ids():
    works = make_works([{"work_id": f"WS/MP1/2024-2025/{i}"} for i in range(10)])
    injected, ids = inject_duplicate_record(works, seed=3, n=4)

    real_ids = set(works["work_id"].to_list())
    assert injected.height == 4
    assert set(ids).issubset(real_ids)
    assert len(set(ids)) == 4


def test_inject_phantom_completion_has_no_expenditure_and_is_marked_complete():
    works = make_works(
        [{"work_id": f"WS/MP1/2024-2025/{i}", "sanction_amount": 100_000.0} for i in range(10)]
    )
    injected, ids = inject_phantom_completion(works, seed=4, n=5)

    assert injected.height == 5
    assert set(injected["work_status"].to_list()) == {"Work Completed"}
    assert set(injected["amount_disbursed_at_completion"].to_list()) == {0.0}
    assert injected["completion_date"].null_count() == 0
    assert set(ids) & set(works["work_id"].to_list()) == set()  # new ids, not real ones


def test_find_concentration_target_picks_most_balanced_eligible_mp():
    rows = []
    # MP_BALANCED: 5 works agency A, 5 works agency B -> 50/50 split, most balanced.
    for i in range(5):
        rows.append({"work_id": f"WS/MPBAL/2024-2025/{i}", "mp_name": "MP_BALANCED", "implementing_agency": "AGENCY_A"})
    for i in range(5):
        rows.append({"work_id": f"WS/MPBAL/2024-2025/{i+5}", "mp_name": "MP_BALANCED", "implementing_agency": "AGENCY_B"})
    # MP_SKEWED: 9 works agency C, 1 work agency D -> already concentrated, should not be picked.
    for i in range(9):
        rows.append({"work_id": f"WS/MPSKEW/2024-2025/{i}", "mp_name": "MP_SKEWED", "implementing_agency": "AGENCY_C"})
    rows.append({"work_id": "WS/MPSKEW/2024-2025/9", "mp_name": "MP_SKEWED", "implementing_agency": "AGENCY_D"})
    works = make_works(rows)

    mp_name, agency = _find_concentration_target(works, min_works_per_mp=10)

    assert mp_name == "MP_BALANCED"
    assert agency in {"AGENCY_A", "AGENCY_B"}


def test_inject_agency_concentration_routes_new_works_to_target_agency():
    rows = []
    for i in range(5):
        rows.append({"work_id": f"WS/MPBAL/2024-2025/{i}", "mp_name": "MP_BALANCED", "implementing_agency": "AGENCY_A"})
    for i in range(5):
        rows.append({"work_id": f"WS/MPBAL/2024-2025/{i+5}", "mp_name": "MP_BALANCED", "implementing_agency": "AGENCY_B"})
    for i in range(9):
        rows.append({"work_id": f"WS/MPSKEW/2024-2025/{i}", "mp_name": "MP_SKEWED", "implementing_agency": "AGENCY_C"})
    rows.append({"work_id": "WS/MPSKEW/2024-2025/9", "mp_name": "MP_SKEWED", "implementing_agency": "AGENCY_D"})
    works = make_works(rows)

    injected, ids = inject_agency_concentration(works, seed=5, n=6)

    assert injected.height == 6
    assert len(set(ids)) == 6
    assert set(injected["mp_name"].to_list()) == {"MP_BALANCED"}
    agencies_used = set(injected["implementing_agency"].to_list())
    assert len(agencies_used) == 1  # every injected work routes to the same single target agency
    assert agencies_used <= {"AGENCY_A", "AGENCY_B"}
