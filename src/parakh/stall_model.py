"""E3 — stall-risk model.

Label: is a work "slow" relative to its own category's normal
completion time (>P75), learned from every category with enough
completed works to make that threshold meaningful (n>=30 — the same
floor peer_stats.py uses everywhere else).

A genuinely open work has three possible states, not two — this
matters for how the label is built:

  - completed: the outcome is known. label = 1 if it took longer than
    its category's P75, else 0.
  - in progress, already past the category's P75 with no completion
    date: the outcome is *already* determined regardless of whether it
    eventually finishes — label = 1 (confirmed stalled).
  - in progress, still within the category's normal window: genuinely
    unknown yet. Excluded from training (right-censored) — labeling
    these one way or the other would just be guessing.

The plan says "the positive class is rare" — checked against the real
corpus before writing a line of model code, and it doesn't hold here.
Combining categories 1 and 2 above gives 65,394 labeled works at a
49.6% positive rate, not rare at all. The reason: in-progress works
are a length-biased sample — a work that finishes quickly spends only
a little calendar time "in progress" before leaving that bucket
entirely, so any snapshot of currently-open works is skewed toward the
slower ones (the classic inspection paradox). PR-AUC is still reported
per the plan (it doesn't hurt to report it), but ROC-AUC is reported
too and isn't misleading at this balance the way it would be for a
genuinely rare event.

The one deliverable the plan actually asks for — "a stall-risk score
for works still in flight" — only has real value for state 3, the
still-within-window works. States 1 (resolved) and 2 (already
confirmed stalled, which B3 already flags deterministically) don't
need a model's opinion. Scoring state 3 is the actual early-warning
signal: which currently-normal-looking works are most likely to become
a B3 flag before they do.
"""

from __future__ import annotations

import datetime as dt

import lightgbm as lgb
import numpy as np
import polars as pl
from sklearn.calibration import calibration_curve
from sklearn.metrics import average_precision_score, roc_auc_score

MIN_CATEGORY_N = 30

_CATEGORICAL_FEATURES = ["category", "state", "financial_year"]
_NUMERIC_FEATURES = [
    "sanction_amount",
    "sanction_month",
    "description_length",
    "description_corrupted",
    "agency_prior_count",
    "mp_prior_count",
]
FEATURE_COLUMNS = _CATEGORICAL_FEATURES + _NUMERIC_FEATURES


def _category_thresholds(works: pl.DataFrame) -> pl.DataFrame:
    completed = works.filter(
        pl.col("sanction_date").is_not_null() & pl.col("completion_date").is_not_null()
    ).with_columns((pl.col("completion_date") - pl.col("sanction_date")).dt.total_days().alias("days_to_complete"))
    return (
        completed.group_by("category")
        .agg(pl.col("days_to_complete").quantile(0.75).alias("p75_days"), pl.len().alias("n"))
        .filter(pl.col("n") >= MIN_CATEGORY_N)
    )


def _add_features(works: pl.DataFrame) -> pl.DataFrame:
    """Features known at sanction time only — nothing derived from
    completion date, payments, or anything else that happens after."""
    ordered = works.sort("sanction_date")
    return ordered.with_columns(
        pl.col("sanction_date").dt.month().alias("sanction_month"),
        pl.col("description").fill_null("").str.len_chars().alias("description_length"),
        pl.col("description_corrupted").fill_null(False).cast(pl.Int8),
        # Prior experience strictly before this work's own sanction —
        # no lookahead: an agency/MP's very first work sees a count of 0.
        (pl.int_range(pl.len()).over("implementing_agency")).alias("agency_prior_count"),
        (pl.int_range(pl.len()).over("mp_name")).alias("mp_prior_count"),
    )


def build_dataset(works: pl.DataFrame, as_of: dt.date | None = None) -> dict[str, pl.DataFrame]:
    """Returns {"labeled": ..., "score": ...}.

    "labeled" is completed + confirmed-stalled works, for training and
    evaluation. "score" is the still-within-window in-progress works —
    the ones a deployed model actually needs to produce a number for.
    """
    as_of = as_of or dt.date.today()
    thresholds = _category_thresholds(works)

    sanctioned = works.filter(pl.col("sanction_date").is_not_null()).join(thresholds, on="category", how="inner")
    sanctioned = _add_features(sanctioned)

    completed = sanctioned.filter(pl.col("completion_date").is_not_null()).with_columns(
        (
            (pl.col("completion_date") - pl.col("sanction_date")).dt.total_days() > pl.col("p75_days")
        ).cast(pl.Int8).alias("label")
    )
    in_progress = sanctioned.filter(pl.col("completion_date").is_null()).with_columns(
        (pl.lit(as_of) - pl.col("sanction_date")).dt.total_days().alias("days_open")
    )
    confirmed_stalled = in_progress.filter(pl.col("days_open") > pl.col("p75_days")).with_columns(
        pl.lit(1, dtype=pl.Int8).alias("label")
    )
    censored = in_progress.filter(pl.col("days_open") <= pl.col("p75_days"))

    keep = ["work_id", "label", *FEATURE_COLUMNS]
    labeled = pl.concat([completed.select(keep), confirmed_stalled.select(keep)], how="vertical_relaxed")

    return {"labeled": labeled, "score": censored.select(["work_id", "days_open", "p75_days", *FEATURE_COLUMNS])}


def _to_lgb_frame(df: pl.DataFrame) -> "object":
    """Polars -> pandas with categorical dtypes LightGBM recognizes natively."""
    pdf = df.select(FEATURE_COLUMNS).to_pandas()
    for c in _CATEGORICAL_FEATURES:
        pdf[c] = pdf[c].astype("category")
    return pdf


def time_split(labeled: pl.DataFrame, works: pl.DataFrame, test_quantile: float = 0.8) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Split by sanction_date, never randomly — the plan's own rule.

    There's only one parliamentary term in this corpus (confirmed
    during recon), so the plan's "split by term" doesn't apply; this
    is the direct within-term analogue — hold out the most recent
    slice of sanctions instead of a random subsample.
    """
    dated = labeled.join(works.select(["work_id", "sanction_date"]), on="work_id")
    cutoff = dated["sanction_date"].quantile(test_quantile)
    train = dated.filter(pl.col("sanction_date") < cutoff).drop("sanction_date")
    test = dated.filter(pl.col("sanction_date") >= cutoff).drop("sanction_date")
    return train, test


def train_and_evaluate(works: pl.DataFrame, as_of: dt.date | None = None) -> dict:
    dataset = build_dataset(works, as_of=as_of)
    labeled = dataset["labeled"]
    train, test = time_split(labeled, works)

    X_train, y_train = _to_lgb_frame(train), train["label"].to_numpy()
    X_test, y_test = _to_lgb_frame(test), test["label"].to_numpy()

    model = lgb.LGBMClassifier(
        n_estimators=200,
        num_leaves=31,
        learning_rate=0.05,
        min_child_samples=50,
        random_state=42,
        verbosity=-1,
    )
    model.fit(X_train, y_train, categorical_feature=_CATEGORICAL_FEATURES)

    proba = model.predict_proba(X_test)[:, 1]
    pr_auc = average_precision_score(y_test, proba)
    roc_auc = roc_auc_score(y_test, proba)
    frac_pos, mean_pred = calibration_curve(y_test, proba, n_bins=10, strategy="quantile")

    importances = dict(zip(X_train.columns, model.feature_importances_.tolist()))

    return {
        "model": model,
        "n_train": train.height,
        "n_test": test.height,
        "positive_rate_train": float(y_train.mean()),
        "positive_rate_test": float(y_test.mean()),
        "pr_auc": float(pr_auc),
        "roc_auc": float(roc_auc),
        "calibration": {"mean_predicted": mean_pred.tolist(), "fraction_positive": frac_pos.tolist()},
        "feature_importances": importances,
        "score_set": dataset["score"],
    }


def score_at_risk_works(model: lgb.LGBMClassifier, score_set: pl.DataFrame) -> pl.DataFrame:
    X = _to_lgb_frame(score_set)
    proba = model.predict_proba(X)[:, 1]
    return score_set.select(["work_id", "days_open", "p75_days"]).with_columns(
        pl.Series("stall_risk", proba)
    ).sort("stall_risk", descending=True)
