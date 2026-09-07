"""Pure Polars-expression parsers for the eSAKSHI raw fields.

Every function here takes a column expression and returns a new
expression — nothing touches a DataFrame directly, so these compose
in a single `.with_columns(...)` in ingest.py and stay independently
unit-testable (see tests/test_parse.py).
"""

from __future__ import annotations

import polars as pl

from parakh.config import UNPARSEABLE_WORK_ID, UNSANCTIONED_WORK_ID

# "WS/MP187/2023-2024/1199-Construction of rooms and halls in school and
# colleges" -> work_id "WS/MP187/2023-2024/1199", category "Construction
# of rooms and halls in school and colleges". Some rows carry a literal
# "NA" in place of the ID (confirmed in recon, not hypothetical) — that
# branch is matched deliberately rather than falling through to null,
# so it's visible as UNPARSEABLE_WORK_ID rather than silently dropped.
#
# \s* after "WS/" tolerates a second confirmed source artifact: a
# literal tab-plus-space injected between "WS/" and "MP<code>" for a
# batch of MPs (e.g. "WS/\t MP620/..."), present identically in both
# this composite field and the Expenditure export's separate "Work ID"
# column — normalize_work_id() strips it from both sides so the same
# logical work still joins correctly across files.
_WORK_ID_PATTERN = r"^((?:WS/\s*MP\d+/\d{4}-\d{4}/\d+)|NA)-(.*)$"

_WHITESPACE = r"\s+"


def normalize_work_id(col: str) -> pl.Expr:
    """Strip whitespace a source export artifact can inject mid-ID.

    Applies to any work_id column, not just ones parsed by
    split_work_field — the Expenditure export's own "Work ID" column
    carries the identical tab-corruption for the identical works.
    """
    return pl.col(col).str.replace_all(_WHITESPACE, "").alias(col)


def split_work_field(col: str = "Work") -> list[pl.Expr]:
    """Split a composite "<work_id>-<category text>" field into two columns.

    Returns [work_id, category_from_id] — the category text is a
    fallback; prefer the file's own "Work category" column when present,
    since that one is a clean enum rather than free text after a dash.
    """
    extracted = pl.col(col).str.extract_groups(_WORK_ID_PATTERN)
    work_id = extracted.struct.field("1").str.replace_all(_WHITESPACE, "")
    category_text = extracted.struct.field("2")
    return [
        pl.when(work_id == "NA")
        .then(pl.lit(UNSANCTIONED_WORK_ID))
        .when(work_id.is_null())
        .then(pl.lit(UNPARSEABLE_WORK_ID))
        .otherwise(work_id)
        .alias("work_id"),
        category_text.alias("category_from_work_field"),
    ]


# "SAMBHAL(DISTRICT MAGISTRAE BHIMNAGAR SAMBHAL_IDA)" -> district
# "SAMBHAL", agency "DISTRICT MAGISTRAE BHIMNAGAR SAMBHAL_IDA". A value
# with no parenthesised agency (seen rarely) yields a null agency rather
# than raising — this is enrichment, not validation, so it degrades.
_IDA_PATTERN = r"^([^(]*)\(([^)]*)\)\s*$"


def split_ida(col: str = "IDA") -> list[pl.Expr]:
    """Split the "<district>(<agency name>)" IDA field into two columns."""
    extracted = pl.col(col).str.extract_groups(_IDA_PATTERN)
    district = extracted.struct.field("1").str.strip_chars()
    agency = extracted.struct.field("2").str.strip_chars()
    return [
        pl.when(district.is_null() | (district == ""))
        .then(pl.col(col))
        .otherwise(district)
        .alias("district_raw"),
        agency.alias("implementing_agency"),
    ]


def parse_amount(col: str) -> pl.Expr:
    """Cast a "₹" amount column to Float64. Blank cells become null."""
    return (
        pl.when(pl.col(col).str.strip_chars() == "")
        .then(None)
        .otherwise(pl.col(col))
        .cast(pl.Float64, strict=False)
        .alias(col)
    )


def parse_date(col: str) -> pl.Expr:
    """Parse eSAKSHI's "DD-Mon-YYYY" date strings (e.g. "14-Jun-2023")."""
    return (
        pl.when(pl.col(col).str.strip_chars() == "")
        .then(None)
        .otherwise(pl.col(col))
        .str.strptime(pl.Date, "%d-%b-%Y", strict=False)
        .alias(col)
    )


# Two or more consecutive "?" is a strong signal of the Devanagira ->
# "?" corruption confirmed in recon (verified at the byte level against
# the raw file, not a decoding artifact on our end) — plain English
# free text essentially never contains "??" for a legitimate reason.
_CORRUPTION_PATTERN = r"\?{2,}"


def flag_description_corruption(col: str = "Work description") -> pl.Expr:
    """True where a description looks like lost-script mojibake, not real text."""
    return (
        pl.col(col)
        .fill_null("")
        .str.contains(_CORRUPTION_PATTERN)
        .alias("description_corrupted")
    )


# "WS/MP187/2023-2024/1199" -> "2023-2024". Deliberately read from the
# work ID rather than derived from a calendar date: this is the
# ministry's own tracking year for the work, which is more meaningful
# for peer comparison than an arbitrary date field, and avoids the
# ambiguity of picking recommended_date vs sanction_date when a work
# crosses a financial-year boundary between the two.
_FY_PATTERN = r"^WS/MP\d+/(\d{4}-\d{4})/\d+$"


def extract_financial_year(col: str = "work_id") -> pl.Expr:
    """Pull the "YYYY-YYYY" financial year straight out of a real work ID.

    Null for anything that isn't a real WS/MP.../seq ID (the two
    sentinels included) — there is no financial year to extract from
    "NOT_YET_SANCTIONED" or "UNPARSEABLE".
    """
    return pl.col(col).str.extract(_FY_PATTERN, 1).alias("financial_year")
