"""Load one raw eSAKSHI export into a typed, house-reconciled Polars frame.

Every loader here does the same four things, in order:
1. read the CSV as all-Utf8 (so messy source values never crash type
   inference — parsing happens explicitly, next);
2. drop the "Grand Total" footer row every export ends with;
3. reconcile the one schema difference between houses — Lok Sabha's
   "Constituency" column sits where Rajya Sabha's "Elected/Nominated"
   column sits (RS members have no constituency) — into two always-
   present, house-appropriate-null columns;
4. tag the frame with house/term/source_file for provenance (§08 of
   the plan: provenance on every screen starts with provenance in the
   data).
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import polars as pl

from parakh import config
from parakh.config import GRAND_TOTAL_MARKER
from parakh.parse import (
    flag_description_corruption,
    normalize_work_id,
    parse_amount,
    parse_date,
    split_ida,
    split_work_field,
)

def _with_ida(df: pl.DataFrame) -> pl.DataFrame:
    return df.with_columns(*split_ida("IDA")) if "IDA" in df.columns else df


def stage_path(house: str, stage: str) -> Path | None:
    """Where this source's export for `stage` lives, or None if absent.

    Absent covers both "the registry never recorded this stage for this
    batch" and "it was recorded but the file is gone from disk".
    """
    try:
        filename = config.files_for(house).get(stage)
    except KeyError:
        return None
    if not filename:
        return None
    path = config.house_terms()[house] / filename
    return path if path.exists() else None


def _read_raw(house: str, stage: str) -> pl.DataFrame:
    path = stage_path(house, stage)
    if path is None:
        raise FileNotFoundError(f"{house!r} has no {stage!r} export on disk")
    df = pl.read_csv(
        path,
        infer_schema_length=0,  # everything as Utf8; we parse explicitly
        encoding="utf8",
    )
    sr_no_col = df.columns[0]
    return df.filter(pl.col(sr_no_col) != GRAND_TOTAL_MARKER)


def _house_member_column(df: pl.DataFrame) -> str:
    for candidate in ("Hon'ble Members of Parliament", "Hon'ble Members of Parliaments"):
        if candidate in df.columns:
            return candidate
    raise KeyError(f"No MP-name column found among {df.columns}")


def _reconcile_house_column(df: pl.DataFrame, house: str) -> pl.DataFrame:
    """Unify LS's "Constituency" / RS's "Elected/Nominated" into two columns."""
    has_constituency = "Constituency" in df.columns
    has_elected = "Elected/Nominated" in df.columns
    return df.with_columns(
        (pl.col("Constituency") if has_constituency else pl.lit(None)).alias("constituency"),
        (pl.col("Elected/Nominated") if has_elected else pl.lit(None)).alias("elected_or_nominated"),
    ).drop([c for c in ("Constituency", "Elected/Nominated") if c in df.columns])


def _add_provenance(df: pl.DataFrame, house: str, stage: str) -> pl.DataFrame:
    return df.with_columns(
        pl.lit(house).alias("house_key"),
        pl.lit(config.house_of(house)).alias("house"),
        pl.lit(config.term_of(house)).alias("term"),
        pl.lit(config.files_for(house)[stage]).alias("source_file"),
    )


def load_recommended(house: str) -> pl.DataFrame:
    df = _read_raw(house, "recommended")
    df = df.rename({_house_member_column(df): "mp_name"})
    df = _reconcile_house_column(df, house)
    df = _with_ida(df)
    df = df.with_columns(
        *split_work_field("WORK" if "WORK" in df.columns else "Work"),
        parse_date("Recommended date"),
        parse_date("Sanction Date"),
        parse_amount("RECOMMENDED AMOUNT   ( ₹ )"),
        flag_description_corruption("Work description"),
    )
    return _add_provenance(df, house, "recommended")


def load_sanctioned(house: str) -> pl.DataFrame:
    df = _read_raw(house, "sanctioned")
    df = df.rename({_house_member_column(df): "mp_name"})
    df = _reconcile_house_column(df, house)
    df = _with_ida(df)
    df = df.with_columns(
        *split_work_field("Work"),
        parse_date("Recommended date"),
        parse_date("Sanction Date"),
        parse_amount("Sanction Amount ( ₹ )"),
        flag_description_corruption("Work description"),
    )
    return _add_provenance(df, house, "sanctioned")


def load_completed(house: str) -> pl.DataFrame:
    df = _read_raw(house, "completed")
    df = df.rename({_house_member_column(df): "mp_name"})
    df = _reconcile_house_column(df, house)
    df = _with_ida(df)
    df = df.with_columns(
        *split_work_field("Work"),
        parse_date("Completion Date"),
        parse_amount("Amount Disbursed ( ₹ )"),
        flag_description_corruption("Work Description"),
        # Confirmed real field (A5): "Images" vs "N/A"/blank — no photo
        # evidence on file for a work marked complete.
        (pl.col("Image").str.strip_chars().str.to_lowercase() == "images").alias("has_image_evidence"),
    )
    return _add_provenance(df, house, "completed")


def load_expenditure(house: str) -> pl.DataFrame:
    df = _read_raw(house, "expenditure")
    df = df.rename({_house_member_column(df): "mp_name", "Work ID": "work_id"})
    df = _reconcile_house_column(df, house)
    df = _with_ida(df)
    df = df.with_columns(
        normalize_work_id("work_id"),
        parse_date("Expenditure Date"),
        parse_amount("Fund Disbursed Amount ( ₹ )"),
    )
    return _add_provenance(df, house, "expenditure")


def load_allocated(house: str) -> pl.DataFrame:
    df = _read_raw(house, "allocated")
    df = df.rename({_house_member_column(df): "mp_name"})
    df = _reconcile_house_column(df, house)
    df = df.with_columns(parse_amount("Allocated AMOUNT ( ₹ )"))
    return _add_provenance(df, house, "allocated")


def load_calamity(house: str) -> pl.DataFrame:
    df = _read_raw(house, "calamity")
    df = df.rename({_house_member_column(df): "mp_name"})
    df = df.with_columns(
        parse_date("Date of Consent"),
        parse_amount("Consent Amount ( ₹ )"),
    )
    return _add_provenance(df, house, "calamity")


STAGE_LOADERS = {
    "recommended": load_recommended,
    "sanctioned": load_sanctioned,
    "completed": load_completed,
    "expenditure": load_expenditure,
    "allocated": load_allocated,
    "calamity": load_calamity,
}


def load_stage_both_houses(stage: str, houses: Iterable[str] | None = None) -> pl.DataFrame:
    """Load one stage for every configured house/term and stack them.

    "Both houses" is now "every registered source": the two built-in
    eSAKSHI house/terms plus any uploaded batch. A batch may carry only
    some of the six exports (only `recommended` is required), so a source
    with no file for this stage is skipped rather than raising — otherwise
    one partial upload would take down the whole pipeline for everyone.

    `houses` narrows the load to specific keys; the corpus-integrity tests
    use it to assert against the built-in exports alone, so that a user's
    upload can never make them fail.
    """
    loader = STAGE_LOADERS[stage]
    keys = list(config.house_terms()) if houses is None else list(houses)
    frames = [loader(house) for house in keys if stage_path(house, stage) is not None]
    if not frames:
        raise FileNotFoundError(f"No source on disk provides the {stage!r} export")
    return pl.concat(frames, how="diagonal_relaxed")
