"""Provenance facts — plan §08, rule 6: source, snapshot date, coverage
on every screen, not buried in a README.

Computed fresh on every `python -m parakh.database` rebuild (same
batch architecture as everything else — see database.py's module
docstring), not hand-maintained, so the numbers can't drift from the
data actually loaded. `snapshot_date` is the date this build ran, not
a date read out of the source files — eSAKSHI's export doesn't carry
one; the portal serves whatever is current at the moment of download,
so "as ingested on <date>" is the honest claim available, not "as of
<date> on the portal's own records".

`houses_covered` used to be a fixed string naming the two built-in
eSAKSHI houses — correct only as long as those were the only two
sources that could ever exist. Once a dataset upload can add a third
(or replace either), a hardcoded string silently goes stale the moment
a batch is added or removed, which is exactly the failure §08 rule 6
exists to prevent. It's derived from the `works` table itself instead,
same as every other number here.
"""

from __future__ import annotations

from datetime import date

import polars as pl

SOURCE_NAME = "eSAKSHI — the MPLADS citizen dashboard"
SOURCE_URL = "https://mplads.mospi.gov.in"


def _format_source(house: str, term: str | None) -> str:
    # A batch added without a term (uploads.py's own placeholder is "—")
    # names just the house rather than rendering an empty/placeholder
    # qualifier.
    if not term or term == "—":
        return house
    return f"{house} ({term} term)"


def _houses_covered(works: pl.DataFrame) -> str:
    pairs = works.select(["house", "term"]).unique().drop_nulls(subset=["house"]).sort("house")
    labels = [_format_source(r["house"], r["term"]) for r in pairs.iter_rows(named=True)]
    return ", ".join(labels) if labels else "no sources loaded"


def build_provenance_record(
    works: pl.DataFrame,
    expenditure: pl.DataFrame,
    allocated: pl.DataFrame,
) -> dict:
    n_works = works.height
    fy_values = sorted(works["financial_year"].drop_nulls().unique().to_list())
    return {
        "source_name": SOURCE_NAME,
        "source_url": SOURCE_URL,
        "houses_covered": _houses_covered(works),
        "snapshot_date": date.today().isoformat(),
        "financial_year_earliest": fy_values[0] if fy_values else None,
        "financial_year_latest": fy_values[-1] if fy_values else None,
        "n_works": n_works,
        "n_expenditure_records": expenditure.height,
        "n_allocated_records": allocated.height,
        "n_states": works.select(pl.col("state").n_unique()).item(),
        "n_mps": works.select(pl.col("mp_name").n_unique()).item(),
        "n_agencies": works.select(pl.col("implementing_agency").n_unique()).item(),
        "quantity_coverage": (
            round(works.filter(pl.col("quantity").is_not_null()).height / n_works, 4) if n_works else 0.0
        ),
        "image_evidence_coverage": (
            round(works.filter(pl.col("has_image_evidence")).height / n_works, 4) if n_works else 0.0
        ),
        "description_corruption_rate": (
            round(works.filter(pl.col("description_corrupted")).height / n_works, 4) if n_works else 0.0
        ),
    }
