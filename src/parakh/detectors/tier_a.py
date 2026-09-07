"""Tier A — deterministic integrity flags.

Every detector here is a pure function:

    (works: pl.DataFrame, expenditure: pl.DataFrame) -> pl.DataFrame

returning the common flag schema: work_id, detector, tier, evidence.
No detector ranks or scores a work — that's Tier C's job. These either
fire or don't, on an arithmetic or logical contradiction a human can
verify by hand from the evidence sentence alone. Vocabulary lock (plan
§08) applies here: evidence text stays factual and neutral — "exceeds",
"recorded", "no evidence on file" — an observation, never an accusation.
"""

from __future__ import annotations

import polars as pl

from parakh.evidence import fmt_inr

TIER = "A"

EMPTY_FLAGS = pl.DataFrame(
    schema={"work_id": pl.Utf8, "detector": pl.Utf8, "tier": pl.Utf8, "evidence": pl.Utf8}
)

# Confirmed against real data during ingestion: two "excess" cases were
# ~1e-10 rupees of float64 rounding noise, not a real overspend — this
# tolerance exists because we checked, not as a defensive guess.
_LEDGER_EPSILON = 1.0

# A2: how much of the sanction has to be unpaid, for a "completed" work,
# before it's worth a human's attention.
_PHANTOM_COMPLETION_THRESHOLD = 0.05


def _flags(rows: list[dict], detector: str) -> pl.DataFrame:
    if not rows:
        return EMPTY_FLAGS.clone()
    return pl.DataFrame(
        {
            "work_id": [r["work_id"] for r in rows],
            "detector": [detector] * len(rows),
            "tier": [TIER] * len(rows),
            "evidence": [r["evidence"] for r in rows],
        }
    )


def a1_ledger_contradiction(works: pl.DataFrame, expenditure: pl.DataFrame) -> pl.DataFrame:
    rows: list[dict] = []

    # 1a: summed payments exceed the sanctioned amount.
    paid = expenditure.group_by("work_id").agg(
        pl.col("amount").sum().alias("total_paid"),
        pl.len().alias("n_payments"),
    )
    over = (
        works.join(paid, on="work_id", how="inner")
        .filter(
            pl.col("sanction_amount").is_not_null()
            & (pl.col("total_paid") > pl.col("sanction_amount") + _LEDGER_EPSILON)
        )
        .select("work_id", "sanction_amount", "total_paid", "n_payments")
    )
    for r in over.iter_rows(named=True):
        excess = r["total_paid"] - r["sanction_amount"]
        rows.append(
            {
                "work_id": r["work_id"],
                "evidence": (
                    f"{r['n_payments']} payment(s) totalling {fmt_inr(r['total_paid'])} recorded "
                    f"against a work sanctioned for {fmt_inr(r['sanction_amount'])} — "
                    f"excess {fmt_inr(excess)}."
                ),
            }
        )

    # 1b: zero or negative sanction on a record that was actually sanctioned.
    bad_sanction = works.filter(
        pl.col("sanction_amount").is_not_null() & (pl.col("sanction_amount") <= 0)
    ).select("work_id", "sanction_amount")
    for r in bad_sanction.iter_rows(named=True):
        rows.append(
            {
                "work_id": r["work_id"],
                "evidence": f"Sanctioned amount on record is {fmt_inr(r['sanction_amount'])} — zero or negative.",
            }
        )

    # 1c: completion recorded before the work was even sanctioned.
    backdated = works.filter(
        pl.col("completion_date").is_not_null()
        & pl.col("sanction_date").is_not_null()
        & (pl.col("completion_date") < pl.col("sanction_date"))
    ).select("work_id", "sanction_date", "completion_date")
    for r in backdated.iter_rows(named=True):
        rows.append(
            {
                "work_id": r["work_id"],
                "evidence": (
                    f"Completion date ({r['completion_date']}) recorded before the "
                    f"sanction date ({r['sanction_date']})."
                ),
            }
        )

    return _flags(rows, "A1")


def a2_phantom_completion(works: pl.DataFrame, expenditure: pl.DataFrame) -> pl.DataFrame:
    paid = expenditure.group_by("work_id").agg(pl.col("amount").sum().alias("total_paid"))
    candidates = (
        works.filter(pl.col("work_status") == "Work Completed")
        .join(paid, on="work_id", how="left")
        .with_columns(pl.col("total_paid").fill_null(0.0))
    )
    flagged = candidates.filter(
        (pl.col("total_paid") == 0.0)
        | (
                pl.col("sanction_amount").is_not_null()
                & (pl.col("sanction_amount") > 0)
                & (pl.col("total_paid") < _PHANTOM_COMPLETION_THRESHOLD * pl.col("sanction_amount"))
        )
    ).select("work_id", "sanction_amount", "total_paid")

    rows = []
    for r in flagged.iter_rows(named=True):
        pct = (r["total_paid"] / r["sanction_amount"] * 100) if r["sanction_amount"] else 0.0
        rows.append(
            {
                "work_id": r["work_id"],
                "evidence": (
                    f"Marked Work Completed, but only {fmt_inr(r['total_paid'])} paid out "
                    f"({pct:.1f}% of the {fmt_inr(r['sanction_amount'])} sanctioned)."
                ),
            }
        )
    return _flags(rows, "A2")


def a3_duplicate_record(works: pl.DataFrame, expenditure: pl.DataFrame) -> pl.DataFrame:
    """The same real work_id appears more than once in the source export.

    The plan originally scoped a second check here — distinct work IDs
    sharing identical description + location + agency + amount within
    a 90-day window. Checked against the real corpus and retired
    before shipping: it fires 8,126 times, dominated by legitimate
    batch recommendations (one MP requesting the same standard item —
    e.g. "Installation of Multi gym equipments in school" — at several
    schools with one templated description; the largest such group is
    118 identical "high-mast light" entries from a single MP in one
    constituency). That is normal MPLADS behaviour, not a duplicate
    submission, and Tier A's whole premise is that a flag here needs
    no peer context to be credible. Telling batch-rollout apart from a
    genuine near-duplicate needs a peer-relative baseline (how large a
    batch is normal for this MP/category) — that's Tier B work, not
    Tier A, and isn't built yet. Only the literal-same-ID case ships
    here; the near-duplicate pattern is a documented gap, not a
    silently dropped one.
    """
    real = works.filter(pl.col("work_id").str.starts_with("WS/"))
    id_counts = real.group_by("work_id").agg(pl.len().alias("n"))
    dup_ids = id_counts.filter(pl.col("n") > 1)

    rows = [
        {
            "work_id": r["work_id"],
            "evidence": f"Work ID appears {r['n']} times in the source export.",
        }
        for r in dup_ids.iter_rows(named=True)
    ]
    return _flags(rows, "A3")


def a4_orphan_sanction(works: pl.DataFrame, expenditure: pl.DataFrame) -> pl.DataFrame:
    flagged = works.filter(
        pl.col("sanction_amount").is_not_null()
        & (
            pl.col("implementing_agency").is_null()
            | pl.col("state").is_null()
            | pl.col("category").is_null()
            | (pl.col("category") == "")
        )
    ).select("work_id", "sanction_amount", "implementing_agency", "state", "category")

    rows = []
    for r in flagged.iter_rows(named=True):
        missing = [
            name
            for name, val in [
                ("implementing agency", r["implementing_agency"]),
                ("state", r["state"]),
                ("category", r["category"]),
            ]
            if val is None or val == ""
        ]
        rows.append(
            {
                "work_id": r["work_id"],
                "evidence": (
                    f"Sanctioned for {fmt_inr(r['sanction_amount'])} but missing: {', '.join(missing)}."
                ),
            }
        )
    return _flags(rows, "A4")


def a5_unverified_completion(works: pl.DataFrame, expenditure: pl.DataFrame) -> pl.DataFrame:
    flagged = works.filter(
        pl.col("completion_date").is_not_null() & (pl.col("has_image_evidence") == False)  # noqa: E712
    ).select("work_id", "completion_date", "amount_disbursed_at_completion")

    rows = [
        {
            "work_id": r["work_id"],
            "evidence": (
                f"Marked complete on {r['completion_date']} "
                f"({fmt_inr(r['amount_disbursed_at_completion'])} disbursed) with no photo evidence on file."
            ),
        }
        for r in flagged.iter_rows(named=True)
    ]
    return _flags(rows, "A5")
