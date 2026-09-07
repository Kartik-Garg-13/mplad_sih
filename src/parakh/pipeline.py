"""Raw eSAKSHI exports -> one canonical works table + supporting tables.

Design (see plan §02): batch, offline, read-only after this point.
Nothing downstream — detectors, API, UI — ever reads a raw CSV; they
read the Parquet this writes. Run with:

    python -m parakh.pipeline
"""

from __future__ import annotations

import polars as pl

from parakh.config import PROCESSED_DIR, UNPARSEABLE_WORK_ID, UNSANCTIONED_WORK_ID
from parakh.ingest import load_stage_both_houses
from parakh.parse import extract_financial_year
from parakh.quantity import extract_quantity

_NON_JOINABLE_IDS = [UNPARSEABLE_WORK_ID, UNSANCTIONED_WORK_ID]

# Recommended is the superset — every work that ever existed starts
# here, whether or not it was ever sanctioned. Sanctioned/Completed
# are left-joined on, so a work not yet sanctioned keeps its recommended
# row with nulls for the fields that don't exist for it yet, rather than
# disappearing.
_RECOMMENDED_KEEP = [
    "work_id",
    # Which source this row came from — a built-in house/term key or an
    # uploaded batch key. Carried all the way to the works table so the UI
    # can show one batch on its own; the other stages' copies are dropped
    # by the joins, so this is the single surviving provenance handle.
    "house_key",
    "house",
    "term",
    "State",
    "district_raw",
    "implementing_agency",
    "mp_name",
    "constituency",
    "elected_or_nominated",
    "Work category",
    "category_from_work_field",
    "Work description",
    "description_corrupted",
    "Recommended date",
    "RECOMMENDED AMOUNT   ( ₹ )",
]

_SANCTIONED_KEEP = [
    "work_id",
    "Sanction Date",
    "Sanction Amount ( ₹ )",
    "Work Status",
]

_COMPLETED_KEEP = [
    "work_id",
    "Completion Date",
    "Amount Disbursed ( ₹ )",
    "has_image_evidence",
]

_RENAME = {
    "State": "state",
    # "Work category" is a near-useless coarse field in practice — 98%
    # of real rows are "Normal/Others" (confirmed against the live
    # output, not assumed). The field that actually carries a usable,
    # closed-ish taxonomy ("Construction of roads...", "Street
    # lights", "Purchase of ambulances...", etc.) is the text parsed
    # out of the work ID field itself — kept as the primary `category`
    # column; the coarse one survives as `category_broad` in case it's
    # useful for some other cut.
    "Work category": "category_broad",
    "category_from_work_field": "category",
    "Work description": "description",
    "Recommended date": "recommended_date",
    "RECOMMENDED AMOUNT   ( ₹ )": "recommended_amount",
    "Sanction Date": "sanction_date",
    "Sanction Amount ( ₹ )": "sanction_amount",
    "Work Status": "work_status",
    "Completion Date": "completion_date",
    "Amount Disbursed ( ₹ )": "amount_disbursed_at_completion",
}


def build_works_table() -> pl.DataFrame:
    recommended = load_stage_both_houses("recommended").select(_RECOMMENDED_KEEP)
    sanctioned = (
        load_stage_both_houses("sanctioned")
        .select(_SANCTIONED_KEEP)
        .filter(~pl.col("work_id").is_in(_NON_JOINABLE_IDS))
        .unique(subset=["work_id"], keep="first")
    )
    completed = (
        load_stage_both_houses("completed")
        .select(_COMPLETED_KEEP)
        .filter(~pl.col("work_id").is_in(_NON_JOINABLE_IDS))
        .unique(subset=["work_id"], keep="first")
    )

    works = (
        recommended.join(sanctioned, on="work_id", how="left")
        .join(completed, on="work_id", how="left")
        .rename(_RENAME)
        .with_columns(extract_financial_year("work_id"))
        .with_columns(*extract_quantity())
    )
    return works


def build_expenditure_table() -> pl.DataFrame:
    """Transaction-level payments — deliberately NOT aggregated here.

    A1 (ledger contradiction) and the vendor graph both need the
    individual rows; summing happens at detector time, not ingest
    time, so no information is thrown away in the canonical layer.
    """
    exp = load_stage_both_houses("expenditure")
    return exp.rename(
        {
            "Work": "work_description_at_payment",
            "State": "state",
            "Expenditure Date": "expenditure_date",
            "Vendor Name": "vendor_name",
            "Payment Status": "payment_status",
            "Fund Disbursed Amount ( ₹ )": "amount",
        }
    )


def build_allocated_table() -> pl.DataFrame:
    alloc = load_stage_both_houses("allocated")
    return alloc.rename(
        {"State": "state", "Allocated AMOUNT ( ₹ )": "allocated_amount"}
    )


def build_calamity_table() -> pl.DataFrame:
    cal = load_stage_both_houses("calamity")
    return cal.rename(
        {
            "Calamity Type": "calamity_type",
            "Calamity Name": "calamity_name",
            "Date of Consent": "date_of_consent",
            "Consent Amount ( ₹ )": "consent_amount",
        }
    )


def run() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    works = build_works_table()
    works.write_parquet(PROCESSED_DIR / "works.parquet")

    expenditure = build_expenditure_table()
    expenditure.write_parquet(PROCESSED_DIR / "expenditure.parquet")

    allocated = build_allocated_table()
    allocated.write_parquet(PROCESSED_DIR / "allocated.parquet")

    calamity = build_calamity_table()
    calamity.write_parquet(PROCESSED_DIR / "calamity.parquet")

    print(f"works:       {works.height:>8,} rows -> works.parquet")
    print(f"expenditure: {expenditure.height:>8,} rows -> expenditure.parquet")
    print(f"allocated:   {allocated.height:>8,} rows -> allocated.parquet")
    print(f"calamity:    {calamity.height:>8,} rows -> calamity.parquet")


if __name__ == "__main__":
    run()
