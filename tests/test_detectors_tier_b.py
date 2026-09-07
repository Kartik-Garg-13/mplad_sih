"""Unit tests for the first Tier B batch — B1, B3, B6, B7 (the plan's
own "need no text work" ordering). Each test builds the smallest
synthetic peer group that can actually trigger min-n abstention
honestly, rather than mocking abstention away."""

from datetime import date

import polars as pl

from parakh.detectors.tier_b import (
    b1_peer_cost_outlier,
    b2_cost_per_unit_outlier,
    b3_stalled_work,
    b4_threshold_bunching,
    b5_work_splitting,
    b6_agency_concentration,
    b7_year_end_bunching,
    b8_near_duplicate_funding,
)

_DEFAULT_WORK = {
    "work_id": "WS/MP001/2024-2025/1",
    "house": "Lok Sabha",
    "term": "18th",
    "state": "Bihar",
    "district_raw": "Patna",
    "implementing_agency": "AGENCY_A",
    "mp_name": "Test MP",
    "constituency": "Test PC",
    "elected_or_nominated": None,
    "category_broad": "Normal/Others",
    "category": "Street lights",
    "description": "Installation of street lights",
    "description_corrupted": False,
    "recommended_date": date(2024, 4, 10),
    "recommended_amount": 100_000.0,
    "sanction_date": date(2024, 4, 20),
    "sanction_amount": 100_000.0,
    "work_status": "Work Completed",
    "completion_date": date(2024, 5, 20),
    "amount_disbursed_at_completion": 100_000.0,
    "has_image_evidence": True,
    "financial_year": "2024-2025",
    "quantity": None,
    "quantity_unit": None,
}

_SCHEMA = {
    "work_id": pl.Utf8, "house": pl.Utf8, "term": pl.Utf8, "state": pl.Utf8,
    "district_raw": pl.Utf8, "implementing_agency": pl.Utf8, "mp_name": pl.Utf8,
    "constituency": pl.Utf8, "elected_or_nominated": pl.Utf8, "category_broad": pl.Utf8,
    "category": pl.Utf8, "description": pl.Utf8, "description_corrupted": pl.Boolean,
    "recommended_date": pl.Date, "recommended_amount": pl.Float64, "sanction_date": pl.Date,
    "sanction_amount": pl.Float64, "work_status": pl.Utf8, "completion_date": pl.Date,
    "amount_disbursed_at_completion": pl.Float64, "has_image_evidence": pl.Boolean,
    "financial_year": pl.Utf8, "quantity": pl.Float64, "quantity_unit": pl.Utf8,
}


def make_works(*overrides: dict) -> pl.DataFrame:
    rows = [{**_DEFAULT_WORK, **o} for o in overrides]
    return pl.DataFrame(rows, schema=_SCHEMA)


EMPTY_EXP = pl.DataFrame(schema={"work_id": pl.Utf8, "amount": pl.Float64})


def _peer_rows(n: int, work_id_prefix: str, **field_overrides) -> list[dict]:
    return [
        {**field_overrides, "work_id": f"{work_id_prefix}{i}"}
        for i in range(n)
    ]


# ---------------------------------------------------------------- B1 ----

def test_b1_flags_outlier_above_peer_group():
    peers = _peer_rows(30, "WS/MP900/2024-2025/", sanction_amount=100_000.0)
    outlier = {"work_id": "WS/MP001/2024-2025/1", "sanction_amount": 500_000.0}
    works = make_works(*peers, outlier)
    flags = b1_peer_cost_outlier(works, EMPTY_EXP)
    assert flags.height == 1
    assert flags["work_id"][0] == "WS/MP001/2024-2025/1"
    assert "5.0x" in flags["evidence"][0]


def test_b1_abstains_below_min_peer_group():
    peers = _peer_rows(10, "WS/MP900/2024-2025/", sanction_amount=100_000.0)  # only 10, need 30
    outlier = {"work_id": "WS/MP001/2024-2025/1", "sanction_amount": 500_000.0}
    works = make_works(*peers, outlier)
    flags = b1_peer_cost_outlier(works, EMPTY_EXP)
    assert flags.height == 0


def test_b1_ignores_unsanctioned_works():
    peers = _peer_rows(30, "WS/MP900/2024-2025/", sanction_amount=100_000.0)
    unsanctioned = {"work_id": "WS/MP001/2024-2025/1", "sanction_amount": None, "sanction_date": None}
    works = make_works(*peers, unsanctioned)
    flags = b1_peer_cost_outlier(works, EMPTY_EXP)
    assert flags.height == 0


# ---------------------------------------------------------------- B2 ----

def test_b2_flags_cost_per_unit_outlier():
    peers = _peer_rows(
        30, "WS/MP900/2024-2025/",
        sanction_amount=100_000.0, quantity=100.0, quantity_unit="meter",
    )  # ₹1,000/meter
    outlier = {
        "work_id": "WS/MP001/2024-2025/1",
        "sanction_amount": 100_000.0,
        "quantity": 10.0,
        "quantity_unit": "meter",
    }  # ₹10,000/meter — 10x peer median
    works = make_works(*peers, outlier)
    flags = b2_cost_per_unit_outlier(works, EMPTY_EXP)
    assert flags.height == 1
    assert flags["work_id"][0] == "WS/MP001/2024-2025/1"
    assert "10.0x" in flags["evidence"][0]


def test_b2_ignores_works_with_no_extracted_quantity():
    peers = _peer_rows(
        30, "WS/MP900/2024-2025/",
        sanction_amount=100_000.0, quantity=100.0, quantity_unit="meter",
    )
    no_quantity = {"work_id": "WS/MP001/2024-2025/1", "sanction_amount": 900_000.0, "quantity": None}
    works = make_works(*peers, no_quantity)
    flags = b2_cost_per_unit_outlier(works, EMPTY_EXP)
    assert flags.height == 0


def test_b2_does_not_compare_across_different_units():
    # 30 meter-priced peers plus 1 litre-priced work at an extreme
    # cost_per_unit — must not be compared against the meter peer
    # group just because they share a category.
    peers = _peer_rows(
        30, "WS/MP900/2024-2025/",
        sanction_amount=100_000.0, quantity=100.0, quantity_unit="meter",
    )
    litre_work = {
        "work_id": "WS/MP001/2024-2025/1",
        "sanction_amount": 100_000.0,
        "quantity": 100.0,
        "quantity_unit": "litre",
    }
    works = make_works(*peers, litre_work)
    flags = b2_cost_per_unit_outlier(works, EMPTY_EXP)
    assert flags.height == 0  # litre group has n=1, abstains


# ---------------------------------------------------------------- B3 ----

def test_b3_flags_work_stalled_well_beyond_peer_p95():
    completed_peers = _peer_rows(
        30, "WS/MP900/2024-2025/",
        sanction_date=date(2024, 1, 1), completion_date=date(2024, 1, 31),  # 30 days each
    )
    stalled = {
        "work_id": "WS/MP001/2024-2025/1",
        "sanction_date": date(2024, 1, 1),
        "completion_date": None,
    }
    works = make_works(*completed_peers, stalled)
    flags = b3_stalled_work(works, EMPTY_EXP, as_of=date(2024, 12, 1))  # ~335 days open
    assert flags.height == 1
    assert flags["work_id"][0] == "WS/MP001/2024-2025/1"


def test_b3_does_not_flag_work_within_normal_range():
    completed_peers = _peer_rows(
        30, "WS/MP900/2024-2025/",
        sanction_date=date(2024, 1, 1), completion_date=date(2024, 1, 31),
    )
    recent = {
        "work_id": "WS/MP001/2024-2025/1",
        "sanction_date": date(2024, 11, 25),
        "completion_date": None,
    }
    works = make_works(*completed_peers, recent)
    flags = b3_stalled_work(works, EMPTY_EXP, as_of=date(2024, 12, 1))  # 6 days open
    assert flags.height == 0


def test_b3_abstains_when_too_few_completed_peers():
    completed_peers = _peer_rows(
        5, "WS/MP900/2024-2025/",  # below min_n
        sanction_date=date(2024, 1, 1), completion_date=date(2024, 1, 31),
    )
    stalled = {"work_id": "WS/MP001/2024-2025/1", "sanction_date": date(2024, 1, 1), "completion_date": None}
    works = make_works(*completed_peers, stalled)
    flags = b3_stalled_work(works, EMPTY_EXP, as_of=date(2024, 12, 1))
    assert flags.height == 0


# ---------------------------------------------------------------- B4 ----
# (Benford digit-conformity tests removed along with the sub-detector
# itself — see b4_threshold_bunching's docstring for why it was
# retired. Threshold bunching is the whole of B4 now.)

def test_b4_flags_bunching_just_under_threshold():
    # 20 works from BUNCHING_AGENCY just under Rs 5,00,000; 20 more
    # spread well away from that band. National baseline (other
    # agencies) has amounts spread evenly, none near the band.
    rows = []
    for i in range(20):
        rows.append({"work_id": f"WS/MPB/2024-2025/{i}", "implementing_agency": "BUNCHING_AGENCY", "sanction_amount": 480_000.0 + i})
    for i in range(20):
        rows.append({"work_id": f"WS/MPB/2024-2025/o{i}", "implementing_agency": "BUNCHING_AGENCY", "sanction_amount": 1_000_000.0 + i * 10_000})
    for m in range(10):
        for i in range(20):
            rows.append(
                {
                    "work_id": f"WS/MPN{m}/2024-2025/{i}",
                    "implementing_agency": f"NORMAL_AGENCY_{m}",
                    "sanction_amount": 1_000_000.0 + i * 50_000 + m * 7_000,
                }
            )
    works = make_works(*rows)
    flags = b4_threshold_bunching(works, EMPTY_EXP, min_n_bunching=30)
    flagged_agencies = set()
    for wid in flags["work_id"].to_list():
        flagged_agencies.add(works.filter(pl.col("work_id") == wid)["implementing_agency"][0])
    assert "BUNCHING_AGENCY" in flagged_agencies
    assert "NORMAL_AGENCY_0" not in flagged_agencies


# ---------------------------------------------------------------- B6 ----

def _mp_agency_rows(mp: str, prefix: str, agency_counts: dict[str, int]) -> list[dict]:
    rows = []
    i = 0
    for agency, n in agency_counts.items():
        for _ in range(n):
            rows.append(
                {
                    "work_id": f"{prefix}{i}",
                    "mp_name": mp,
                    "implementing_agency": agency,
                    "sanction_amount": 100_000.0,
                }
            )
            i += 1
    return rows


def test_b6_flags_mp_with_unusually_concentrated_agency():
    rows = []
    # 20 "normal" MPs, roughly even split across two agencies.
    for m in range(20):
        rows += _mp_agency_rows(
            f"Normal MP {m}", f"WS/MP{m}/2024-2025/",
            {"AGENCY_A": 8, "AGENCY_B": 7},
        )
    # One MP whose works are almost entirely with a single agency.
    rows += _mp_agency_rows(
        "Concentrated MP", "WS/MP999/2024-2025/",
        {"AGENCY_X": 14, "AGENCY_Y": 1},
    )
    works = make_works(*rows)
    flags = b6_agency_concentration(works, EMPTY_EXP, min_works_per_mp=10)
    flagged_mps = set()
    for wid in flags["work_id"].to_list():
        flagged_mps.add(works.filter(pl.col("work_id") == wid)["mp_name"][0])
    assert "Concentrated MP" in flagged_mps
    assert "Normal MP 0" not in flagged_mps


def test_b6_ignores_single_agency_mp_even_with_many_works():
    # Confirmed against the real corpus: 27.6% of MPs with >=10 works
    # route 100% of value through one agency because their constituency
    # sits in a single district with one IDA — no choice of agency at
    # all. Flagging that as "concentration" would flood the detector
    # with normal administrative structure.
    rows = []
    for m in range(20):
        rows += _mp_agency_rows(f"Normal MP {m}", f"WS/MP{m}/2024-2025/", {"AGENCY_A": 8, "AGENCY_B": 7})
    rows += _mp_agency_rows("Single Agency MP", "WS/MP999/2024-2025/", {"AGENCY_X": 20})
    works = make_works(*rows)
    flags = b6_agency_concentration(works, EMPTY_EXP, min_works_per_mp=10)
    flagged_mps = {works.filter(pl.col("work_id") == wid)["mp_name"][0] for wid in flags["work_id"].to_list()}
    assert "Single Agency MP" not in flagged_mps


def test_b6_ignores_mp_below_min_works_threshold():
    rows = []
    for m in range(20):
        rows += _mp_agency_rows(f"Normal MP {m}", f"WS/MP{m}/2024-2025/", {"AGENCY_A": 8, "AGENCY_B": 7})
    # Only 3 works total — should not be eligible even though 100% one agency.
    rows += _mp_agency_rows("Tiny MP", "WS/MP999/2024-2025/", {"AGENCY_X": 3})
    works = make_works(*rows)
    flags = b6_agency_concentration(works, EMPTY_EXP, min_works_per_mp=10)
    flagged_mps = {works.filter(pl.col("work_id") == wid)["mp_name"][0] for wid in flags["work_id"].to_list()}
    assert "Tiny MP" not in flagged_mps


# ---------------------------------------------------------------- B7 ----

def _mp_fy_rows(mp: str, prefix: str, fy: str, n_year_end: int, n_other: int) -> list[dict]:
    rows = []
    for i in range(n_year_end):
        rows.append(
            {"work_id": f"{prefix}ye{i}", "mp_name": mp, "financial_year": fy, "sanction_date": date(2025, 2, 15)}
        )
    for i in range(n_other):
        rows.append(
            {"work_id": f"{prefix}o{i}", "mp_name": mp, "financial_year": fy, "sanction_date": date(2024, 6, 1)}
        )
    return rows


def test_b7_flags_year_end_bunched_mp():
    rows = []
    for m in range(20):
        rows += _mp_fy_rows(f"Normal MP {m}", f"WS/MP{m}/2024-2025/", "2024-2025", n_year_end=3, n_other=12)
    rows += _mp_fy_rows("Bunched MP", "WS/MP999/2024-2025/", "2024-2025", n_year_end=14, n_other=1)
    works = make_works(*rows)
    flags = b7_year_end_bunching(works, EMPTY_EXP, min_sanctions_per_fy=10)
    flagged_mps = {works.filter(pl.col("work_id") == wid)["mp_name"][0] for wid in flags["work_id"].to_list()}
    assert "Bunched MP" in flagged_mps
    assert "Normal MP 0" not in flagged_mps


def test_b7_ignores_mp_below_min_sanctions_in_fy():
    rows = []
    for m in range(20):
        rows += _mp_fy_rows(f"Normal MP {m}", f"WS/MP{m}/2024-2025/", "2024-2025", n_year_end=3, n_other=12)
    rows += _mp_fy_rows("Tiny MP", "WS/MP999/2024-2025/", "2024-2025", n_year_end=2, n_other=0)
    works = make_works(*rows)
    flags = b7_year_end_bunching(works, EMPTY_EXP, min_sanctions_per_fy=10)
    flagged_mps = {works.filter(pl.col("work_id") == wid)["mp_name"][0] for wid in flags["work_id"].to_list()}
    assert "Tiny MP" not in flagged_mps


# ---------------------------------------------------------------- B8 ----

_B8_SHARED_BASE = (
    "Construction of high mast light with four LED bulbs and solar panel backup system "
    "at village Ramnagar block Patna near the government primary school building compound wall"
)


def test_b8_flags_near_duplicate_descriptions_same_district():
    # Verified similarity ~0.93 — inside [0.90, 0.999): similar enough
    # to flag, not so identical it reads as the known boilerplate
    # pattern this detector deliberately excludes.
    works = make_works(
        {"work_id": "WS/MP001/2024-2025/1", "district_raw": "Patna", "description": _B8_SHARED_BASE + " road"},
        {"work_id": "WS/MP002/2024-2025/2", "district_raw": "Patna", "description": _B8_SHARED_BASE + " path"},
    )
    flags = b8_near_duplicate_funding(works, EMPTY_EXP)
    assert flags.height == 2
    assert set(flags["work_id"].to_list()) == {"WS/MP001/2024-2025/1", "WS/MP002/2024-2025/2"}


def test_b8_ignores_dissimilar_descriptions():
    works = make_works(
        {"work_id": "WS/MP001/2024-2025/1", "district_raw": "Patna", "description": "Construction of CC road from house to house"},
        {"work_id": "WS/MP002/2024-2025/2", "district_raw": "Patna", "description": "Purchase of mobile water tanker capacity 3000 litres"},
    )
    flags = b8_near_duplicate_funding(works, EMPTY_EXP)
    assert flags.height == 0


def test_b8_excludes_near_exact_boilerplate_batch():
    # The A3 lesson applied here: verbatim-identical descriptions across
    # many works is the normal bulk-recommendation pattern, not evidence.
    rows = [
        {
            "work_id": f"WS/MP00{i}/2024-2025/{i}",
            "district_raw": "Patna",
            "description": "Installation of High Mast Light at Panrui Bazar",
        }
        for i in range(5)
    ]
    works = make_works(*rows)
    flags = b8_near_duplicate_funding(works, EMPTY_EXP)
    assert flags.height == 0


def test_b8_ignores_pairs_outside_time_window():
    works = make_works(
        {
            "work_id": "WS/MP001/2024-2025/1",
            "district_raw": "Patna",
            "description": _B8_SHARED_BASE + " road",
            "recommended_date": date(2024, 1, 1),
        },
        {
            "work_id": "WS/MP002/2024-2025/2",
            "district_raw": "Patna",
            "description": _B8_SHARED_BASE + " path",
            "recommended_date": date(2025, 6, 1),  # well over 180 days later
        },
    )
    flags = b8_near_duplicate_funding(works, EMPTY_EXP)
    assert flags.height == 0


def test_b8_ignores_different_districts():
    works = make_works(
        {"work_id": "WS/MP001/2024-2025/1", "district_raw": "Patna", "description": "Construction of high mast light at village Ramnagar near the temple"},
        {"work_id": "WS/MP002/2024-2025/2", "district_raw": "Gaya", "description": "Construction of high mast light at village Ramnagar close to the temple"},
    )
    flags = b8_near_duplicate_funding(works, EMPTY_EXP)
    assert flags.height == 0


# ---------------------------------------------------------------- B5 ----

# Verified similarity ~0.87 across every pair for n=4 with this base
# and a two-character-or-longer differing suffix (TfidfVectorizer's
# default tokenizer drops single-character tokens, so a single-digit
# suffix collapses to an identical, ceiling-excluded string) — inside
# B5's [0.85, 0.999) band: similar enough to cluster, not identical.
_B5_SHARED_BASE = (
    "Installation of high mast light with four LED bulbs and solar panel backup system "
    "complete work at site number close to main road junction"
)


def _split_candidate_rows(agency: str, district: str, n: int, amount: float, base_date: date) -> list[dict]:
    rows = []
    for i in range(n):
        rows.append(
            {
                "work_id": f"WS/MPsplit{i}/2024-2025/{i}",
                "implementing_agency": agency,
                "district_raw": district,
                "description": f"{_B5_SHARED_BASE} {10 + i}",
                "recommended_date": base_date,
                "recommended_amount": amount,
            }
        )
    return rows


def test_b5_flags_comparably_sized_cluster_within_window():
    rows = _split_candidate_rows("AGENCY_X", "Patna", 4, 100_000.0, date(2024, 3, 1))
    works = make_works(*rows)
    flags = b5_work_splitting(works, EMPTY_EXP)
    assert flags.height == 4


def test_b5_does_not_flag_when_one_work_dominates_the_cluster():
    rows = _split_candidate_rows("AGENCY_X", "Patna", 3, 10_000.0, date(2024, 3, 1))
    # A fourth, much larger work in the same similarity cluster —
    # dominates the total, so this reads as one real project with
    # incidental satellite works, not comparable split pieces.
    rows.append(
        {
            "work_id": "WS/MPsplit99/2024-2025/99",
            "implementing_agency": "AGENCY_X",
            "district_raw": "Patna",
            "description": f"{_B5_SHARED_BASE} 99",
            "recommended_date": date(2024, 3, 1),
            "recommended_amount": 5_000_000.0,
        }
    )
    works = make_works(*rows)
    flags = b5_work_splitting(works, EMPTY_EXP)
    assert flags.height == 0


def test_b5_does_not_flag_outside_time_window():
    rows = _split_candidate_rows("AGENCY_X", "Patna", 2, 100_000.0, date(2024, 3, 1))
    rows += _split_candidate_rows("AGENCY_X", "Patna", 2, 100_000.0, date(2024, 9, 1))
    works = make_works(*rows)
    flags = b5_work_splitting(works, EMPTY_EXP)
    assert flags.height == 0


def test_b5_does_not_flag_fewer_than_three():
    rows = _split_candidate_rows("AGENCY_X", "Patna", 2, 100_000.0, date(2024, 3, 1))
    works = make_works(*rows)
    flags = b5_work_splitting(works, EMPTY_EXP)
    assert flags.height == 0


def test_b5_excludes_near_exact_boilerplate_batch():
    rows = [
        {
            "work_id": f"WS/MPbp{i}/2024-2025/{i}",
            "implementing_agency": "AGENCY_X",
            "district_raw": "Patna",
            "description": "Installation of high mast light",  # verbatim identical
            "recommended_date": date(2024, 3, 1),
            "recommended_amount": 100_000.0,
        }
        for i in range(5)
    ]
    works = make_works(*rows)
    flags = b5_work_splitting(works, EMPTY_EXP)
    assert flags.height == 0
