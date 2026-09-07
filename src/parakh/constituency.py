"""E1 — constituency implementation scorecard.

Lok-Sabha-shaped rows only — anything that structurally carries a real
constituency, tested via `constituency IS NOT NULL` rather than a
`house == "Lok Sabha"` string match. Confirmed during the original
data-source recon: Rajya Sabha members have no constituency at all, so
"constituency scorecard" only has meaning where one exists — RS stays
in the detector corpus and the agency graph, just not here.

The structural test matters once a source is more than the two
built-in eSAKSHI house/terms (see uploads.py): a `house == "Lok Sabha"`
match would silently exclude an uploaded Lok-Sabha-shaped batch that
happens to be labelled anything else ("Pilot District", a later term's
own name, ...), and — worse — would silently *merge* an uploaded batch
into the real Lok Sabha's aggregates if a user happened to label it
"Lok Sabha" verbatim. `constituency` is populated purely by whether the
source CSV carried a Constituency column at all (ingest.py's own
house-column reconciliation), independent of whatever label the batch
was given — confirmed against the real corpus: constituency is
non-null for exactly the Lok Sabha rows and exactly zero Rajya Sabha
rows, in every one of works/expenditure/allocated.

Two things the plan asked for are deliberately not built, for the same
underlying reason: no source for them exists in the ingested corpus,
and acquiring one is a new data-sourcing project, not a Day 10 task.

  - The choropleth map. The plan's own §06 cut order already lists
    this as the second thing to drop under time pressure ("GeoJSON
    boundary wrangling burns a day for a decorative gain") — no PC
    boundary GeoJSON was ever pulled, so this isn't a corner cut
    under pressure, it's the plan's own pre-agreed call, exercised.
  - "Works-per-lakh-population" needs a constituency population
    figure (2011 Census or similar), which was never part of any
    eSAKSHI export and isn't in this corpus in any form. Left out
    rather than faked with a placeholder.

Everything else in the plan's list is real, computed from data already
in hand: completion rate, median time-to-complete, fund utilisation,
unspent balance, and sector (category) mix.
"""

from __future__ import annotations

import polars as pl


def compute_constituency_scorecard(works: pl.DataFrame, expenditure: pl.DataFrame, allocated: pl.DataFrame) -> pl.DataFrame:
    ls_works = works.filter(pl.col("constituency").is_not_null())
    sanctioned = ls_works.filter(pl.col("sanction_amount").is_not_null())

    core = sanctioned.group_by(["state", "constituency"]).agg(
        pl.len().alias("n_sanctioned"),
        pl.col("sanction_amount").sum().alias("total_sanctioned"),
        pl.col("completion_date").is_not_null().sum().alias("n_completed"),
    ).with_columns((pl.col("n_completed") / pl.col("n_sanctioned")).alias("completion_rate"))

    completion_times = (
        sanctioned.filter(pl.col("completion_date").is_not_null())
        .with_columns((pl.col("completion_date") - pl.col("sanction_date")).dt.total_days().alias("days_to_complete"))
        .group_by(["state", "constituency"])
        .agg(pl.col("days_to_complete").median().alias("median_days_to_complete"))
    )

    # Dominant category (by sanctioned-work count) and its share of the
    # constituency's own works — "sector mix" collapsed to the one
    # figure a scorecard row can show; the full breakdown is a detail-
    # view concern, not this table's.
    by_category = sanctioned.group_by(["state", "constituency", "category"]).agg(pl.len().alias("n"))
    dominant_category = (
        by_category.sort("n", descending=True)
        .group_by(["state", "constituency"])
        .agg(pl.col("category").first().alias("dominant_category"), pl.col("n").first().alias("dominant_category_n"))
    )

    exp_by_pc = (
        expenditure.filter(pl.col("constituency").is_not_null())
        .group_by(["state", "constituency"])
        .agg(pl.col("amount").sum().alias("total_expended"))
    )

    # Sum rather than assume one row per constituency: a mid-term MP
    # replacement (confirmed real case — Maharashtra/NANDED) leaves a
    # stale record with a null allocated_amount behind; summing with
    # null treated as 0 collapses it to the real, current figure
    # without a fragile "keep the latest row" heuristic.
    alloc_by_pc = (
        allocated.filter(pl.col("constituency").is_not_null())
        .with_columns(pl.col("allocated_amount").fill_null(0.0))
        .group_by(["state", "constituency"])
        .agg(pl.col("allocated_amount").sum().alias("allocated_amount"), pl.col("mp_name").first().alias("mp_name"))
    )

    scorecard = (
        alloc_by_pc.join(core, on=["state", "constituency"], how="left")
        .join(completion_times, on=["state", "constituency"], how="left")
        .join(dominant_category.select(["state", "constituency", "dominant_category", "dominant_category_n"]), on=["state", "constituency"], how="left")
        .join(exp_by_pc, on=["state", "constituency"], how="left")
    )

    scorecard = scorecard.with_columns(
        pl.col("n_sanctioned").fill_null(0),
        pl.col("n_completed").fill_null(0),
        pl.col("total_sanctioned").fill_null(0.0),
        pl.col("total_expended").fill_null(0.0),
        pl.col("dominant_category_n").fill_null(0),
    ).with_columns(
        (pl.col("dominant_category_n") / pl.col("n_sanctioned").clip(lower_bound=1)).alias("dominant_category_share"),
        pl.when(pl.col("allocated_amount") > 0)
        .then(pl.col("total_expended") / pl.col("allocated_amount"))
        .otherwise(None)
        .alias("fund_utilisation"),
        (pl.col("allocated_amount") - pl.col("total_expended")).alias("unspent_balance"),
    )

    return scorecard
