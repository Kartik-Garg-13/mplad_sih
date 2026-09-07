"""Unit tests for the Tier A detectors — one clean-passing case and one
triggering case per detector, plus the registry-level sanity check that
an all-clean corpus produces zero flags."""

from datetime import date

import polars as pl
import pytest

from parakh.detectors import run_all
from parakh.detectors.tier_a import (
    a1_ledger_contradiction,
    a2_phantom_completion,
    a3_duplicate_record,
    a4_orphan_sanction,
    a5_unverified_completion,
)

_DEFAULT_WORK = {
    "work_id": "WS/MP001/2024-2025/1",
    "house": "Lok Sabha",
    "term": "18th",
    "state": "Bihar",
    "district_raw": "Patna",
    "implementing_agency": "DISTRICT PLANNING OFFICER PATNA_IDA",
    "mp_name": "Test MP",
    "constituency": "Test PC",
    "elected_or_nominated": None,
    "category_broad": "Normal/Others",
    "category": "Street lights",
    "description": "Installation of street lights",
    "description_corrupted": False,
    "recommended_date": date(2024, 1, 1),
    "recommended_amount": 100_000.0,
    "sanction_date": date(2024, 2, 1),
    "sanction_amount": 100_000.0,
    "work_status": "Work Completed",
    "completion_date": date(2024, 6, 1),
    "amount_disbursed_at_completion": 100_000.0,
    "has_image_evidence": True,
    "financial_year": "2024-2025",
    "quantity": None,
    "quantity_unit": None,
}

_WORKS_SCHEMA = {
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


def make_works(*overrides: dict) -> pl.DataFrame:
    rows = [{**_DEFAULT_WORK, **o} for o in overrides]
    return pl.DataFrame(rows, schema=_WORKS_SCHEMA)


def make_expenditure(*rows: tuple[str, float]) -> pl.DataFrame:
    if not rows:
        return pl.DataFrame(schema={"work_id": pl.Utf8, "amount": pl.Float64})
    return pl.DataFrame(
        {"work_id": [r[0] for r in rows], "amount": [r[1] for r in rows]}
    )


EMPTY_EXP = make_expenditure()


# ---------------------------------------------------------------- A1 ----

def test_a1_flags_expenditure_exceeding_sanction():
    works = make_works({"work_id": "W1", "sanction_amount": 100_000.0})
    exp = make_expenditure(("W1", 60_000.0), ("W1", 60_000.0))  # 120k > 100k
    flags = a1_ledger_contradiction(works, exp)
    assert flags.height == 1
    assert flags["detector"][0] == "A1"
    assert "excess" in flags["evidence"][0]


def test_a1_tolerates_float_rounding_noise():
    # Confirmed in the real corpus: two cases were ~1e-10 rupees of
    # float64 rounding, not a real overspend.
    works = make_works({"work_id": "W1", "sanction_amount": 100_000.0})
    exp = make_expenditure(("W1", 99_999.999999999))
    flags = a1_ledger_contradiction(works, exp)
    assert flags.height == 0


def test_a1_flags_nonpositive_sanction():
    works = make_works({"work_id": "W1", "sanction_amount": 0.0})
    flags = a1_ledger_contradiction(works, EMPTY_EXP)
    assert flags.height == 1
    assert flags["work_id"][0] == "W1"


def test_a1_flags_completion_before_sanction():
    works = make_works(
        {
            "work_id": "W1",
            "sanction_date": date(2024, 6, 1),
            "completion_date": date(2024, 1, 1),
        }
    )
    flags = a1_ledger_contradiction(works, EMPTY_EXP)
    assert flags.height == 1


def test_a1_clean_record_not_flagged():
    works = make_works({"work_id": "W1"})
    exp = make_expenditure(("W1", 100_000.0))
    flags = a1_ledger_contradiction(works, exp)
    assert flags.height == 0


# ---------------------------------------------------------------- A2 ----

def test_a2_flags_completed_with_no_payment():
    works = make_works({"work_id": "W1", "work_status": "Work Completed"})
    flags = a2_phantom_completion(works, EMPTY_EXP)
    assert flags.height == 1


def test_a2_flags_completed_with_token_payment():
    works = make_works(
        {"work_id": "W1", "work_status": "Work Completed", "sanction_amount": 1_000_000.0}
    )
    exp = make_expenditure(("W1", 10_000.0))  # 1% of sanction
    flags = a2_phantom_completion(works, exp)
    assert flags.height == 1


def test_a2_not_flagged_when_paid_matches_completion():
    works = make_works({"work_id": "W1", "work_status": "Work Completed", "sanction_amount": 100_000.0})
    exp = make_expenditure(("W1", 100_000.0))
    flags = a2_phantom_completion(works, exp)
    assert flags.height == 0


def test_a2_ignores_works_not_marked_completed():
    works = make_works({"work_id": "W1", "work_status": "Physical Inspection"})
    flags = a2_phantom_completion(works, EMPTY_EXP)
    assert flags.height == 0


# ---------------------------------------------------------------- A3 ----

def test_a3_flags_repeated_work_id():
    works = make_works(
        {"work_id": "WS/MP001/2024-2025/1"},
        {"work_id": "WS/MP001/2024-2025/1"},
    )
    flags = a3_duplicate_record(works, EMPTY_EXP)
    assert flags.height == 1
    assert flags["work_id"][0] == "WS/MP001/2024-2025/1"
    assert "appears 2 times" in flags["evidence"][0]


def test_a3_does_not_flag_distinct_ids_with_identical_content():
    # Deliberately NOT flagged, and this is the point of the test, not
    # an oversight: checked against the real corpus, "identical
    # description + location + agency + amount, different work IDs"
    # is dominated by legitimate batch recommendations (one MP
    # requesting the same standard item at many sites with one
    # templated description — the largest real example is 118
    # identical "high-mast light" entries from a single MP). A3 is
    # Tier A precisely because it needs no peer context to be
    # credible; telling a real near-duplicate apart from a normal
    # batch rollout needs one, so that check isn't here (see the
    # docstring on a3_duplicate_record).
    works = make_works(
        {
            "work_id": "WS/MP001/2024-2025/1",
            "description": "Construction of CC road",
            "recommended_date": date(2024, 1, 1),
        },
        {
            "work_id": "WS/MP001/2024-2025/2",
            "description": "Construction of CC road",
            "recommended_date": date(2024, 1, 2),
        },
    )
    flags = a3_duplicate_record(works, EMPTY_EXP)
    assert flags.height == 0


# ---------------------------------------------------------------- A4 ----

def test_a4_flags_sanctioned_work_missing_agency():
    works = make_works({"work_id": "W1", "implementing_agency": None})
    flags = a4_orphan_sanction(works, EMPTY_EXP)
    assert flags.height == 1
    assert "implementing agency" in flags["evidence"][0]


def test_a4_ignores_unsanctioned_work_missing_agency():
    works = make_works({"work_id": "W1", "implementing_agency": None, "sanction_amount": None})
    flags = a4_orphan_sanction(works, EMPTY_EXP)
    assert flags.height == 0


def test_a4_clean_record_not_flagged():
    works = make_works({"work_id": "W1"})
    flags = a4_orphan_sanction(works, EMPTY_EXP)
    assert flags.height == 0


# ---------------------------------------------------------------- A5 ----

def test_a5_flags_completed_without_image():
    works = make_works({"work_id": "W1", "completion_date": date(2024, 6, 1), "has_image_evidence": False})
    flags = a5_unverified_completion(works, EMPTY_EXP)
    assert flags.height == 1


def test_a5_ignores_not_yet_completed():
    works = make_works({"work_id": "W1", "completion_date": None, "has_image_evidence": None})
    flags = a5_unverified_completion(works, EMPTY_EXP)
    assert flags.height == 0


def test_a5_clean_record_not_flagged():
    works = make_works({"work_id": "W1", "has_image_evidence": True})
    flags = a5_unverified_completion(works, EMPTY_EXP)
    assert flags.height == 0


# ------------------------------------------------------------ registry ----

def test_run_all_on_fully_clean_corpus_yields_no_flags():
    works = make_works(
        {"work_id": "WS/MP001/2024-2025/1"},
        {"work_id": "WS/MP002/2024-2025/1", "description": "Different work entirely"},
    )
    exp = make_expenditure(("WS/MP001/2024-2025/1", 100_000.0), ("WS/MP002/2024-2025/1", 100_000.0))
    flags = run_all(works, exp)
    assert flags.height == 0


def test_run_all_combines_every_detector():
    works = make_works(
        {"work_id": "W1", "sanction_amount": 0.0},  # A1
        {"work_id": "W2", "work_status": "Work Completed"},  # A2 (no payment)
        {"work_id": "W3", "implementing_agency": None},  # A4
        {"work_id": "W4", "completion_date": date(2024, 6, 1), "has_image_evidence": False},  # A5
    )
    flags = run_all(works, EMPTY_EXP)
    assert set(flags["detector"].to_list()) == {"A1", "A2", "A4", "A5"}
    assert flags.columns == ["work_id", "detector", "tier", "evidence"]
