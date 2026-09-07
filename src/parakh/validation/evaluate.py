"""Runs the synthetic-injection corpus through the real detector suite
and scores the result — plan §07 method 1.

Ranking for precision@k / recall@k reuses the flag list's own default
ordering (has_tier_a desc, then n_flags desc) rather than inventing a
score for validation alone: there is no trained composite score in
this app (Tier C — the plan's C3 "Review Priority Score" — was never
built; see /methodology), so the one ranking rule that already ships
is the honest one to validate against.
"""

from __future__ import annotations

import polars as pl

from parakh.detectors import run_all
from parakh.validation.synthetic_injection import TARGET_DETECTOR, build_synthetic_corpus

DEFAULT_K_VALUES = [50, 100, 200, 500, 1000]


def _rank_works(flags: pl.DataFrame) -> pl.DataFrame:
    summary = flags.group_by("work_id").agg(
        pl.len().alias("n_flags"),
        (pl.col("tier") == "A").any().alias("has_tier_a"),
        pl.col("detector").alias("detectors"),
    )
    return summary.sort(["has_tier_a", "n_flags"], descending=[True, True]).with_row_index("rank", offset=1)


def evaluate_synthetic_injection(
    works: pl.DataFrame,
    expenditure: pl.DataFrame,
    seed: int = 20260904,
    k_values: list[int] | None = None,
) -> dict:
    k_values = k_values or DEFAULT_K_VALUES
    augmented, ground_truth = build_synthetic_corpus(works, seed=seed)
    flags = run_all(augmented, expenditure)

    injected_ids = set(ground_truth["work_id"].to_list())

    # Per-type recall: did the type's designed detector fire on that row.
    flags_by_id: dict[str, set[str]] = {}
    for work_id, detector in flags.select("work_id", "detector").iter_rows():
        flags_by_id.setdefault(work_id, set()).add(detector)

    per_type = []
    for injected_type, target_detector in TARGET_DETECTOR.items():
        type_ids = ground_truth.filter(pl.col("injected_type") == injected_type)["work_id"].to_list()
        n = len(type_ids)
        hit_target = sum(1 for wid in type_ids if target_detector in flags_by_id.get(wid, set()))
        hit_any = sum(1 for wid in type_ids if flags_by_id.get(wid))
        per_type.append(
            {
                "injected_type": injected_type,
                "target_detector": target_detector,
                "n_injected": n,
                "recall_target_detector": round(hit_target / n, 4) if n else 0.0,
                "recall_any_detector": round(hit_any / n, 4) if n else 0.0,
            }
        )

    # Overall precision@k / recall@k using the flag list's default ranking.
    ranked = _rank_works(flags).with_columns(pl.col("work_id").is_in(injected_ids).alias("is_synthetic"))
    n_injected_total = len(injected_ids)

    at_k = []
    for k in k_values:
        top_k = ranked.filter(pl.col("rank") <= k)
        n_synthetic_in_top_k = top_k["is_synthetic"].sum()
        at_k.append(
            {
                "k": k,
                "precision_at_k": round(n_synthetic_in_top_k / min(k, ranked.height), 4) if ranked.height else 0.0,
                "recall_at_k": round(n_synthetic_in_top_k / n_injected_total, 4) if n_injected_total else 0.0,
            }
        )

    return {
        "n_injected_total": n_injected_total,
        "n_flagged_total": ranked.height,
        "per_type": per_type,
        "at_k": at_k,
    }


if __name__ == "__main__":
    import polars as pl

    from parakh.config import PROCESSED_DIR

    _works = pl.read_parquet(PROCESSED_DIR / "works.parquet")
    _expenditure = pl.read_parquet(PROCESSED_DIR / "expenditure.parquet")
    _result = evaluate_synthetic_injection(_works, _expenditure)

    print(f"injected: {_result['n_injected_total']}, flagged (incl. real corpus): {_result['n_flagged_total']}")
    print()
    print(f"{'type':<24}{'detector':<10}{'n':>6}{'recall(target)':>16}{'recall(any)':>14}")
    for row in _result["per_type"]:
        print(
            f"{row['injected_type']:<24}{row['target_detector']:<10}{row['n_injected']:>6}"
            f"{row['recall_target_detector']:>16.1%}{row['recall_any_detector']:>14.1%}"
        )
    print()
    print(f"{'k':>8}{'precision@k':>14}{'recall@k':>12}")
    for row in _result["at_k"]:
        print(f"{row['k']:>8}{row['precision_at_k']:>14.1%}{row['recall_at_k']:>12.1%}")
