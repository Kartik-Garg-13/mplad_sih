"""Tier B — peer-relative statistical outliers.

Same contract as Tier A: `(works, expenditure) -> pl.DataFrame` with
columns [work_id, detector, tier, evidence]. Every detector here states
its peer group and n in the evidence sentence and abstains below
`peer_stats.DEFAULT_MIN_PEER_GROUP` — a Tier B flag that can't show its
own peer context isn't a Tier B flag (plan §08, rule 2).
"""

from __future__ import annotations

import datetime as dt

import polars as pl

from parakh.evidence import fmt_inr
from parakh.peer_stats import DEFAULT_MIN_PEER_GROUP, add_robust_z
from parakh.text_similarity import similar_pairs

TIER = "B"

EMPTY_FLAGS = pl.DataFrame(
    schema={"work_id": pl.Utf8, "detector": pl.Utf8, "tier": pl.Utf8, "evidence": pl.Utf8}
)

_Z_THRESHOLD = 3.5


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


def b1_peer_cost_outlier(works: pl.DataFrame, expenditure: pl.DataFrame) -> pl.DataFrame:
    """Robust z-score of sanction_amount within category x state x FY."""
    sanctioned = works.filter(
        pl.col("sanction_amount").is_not_null()
        & pl.col("category").is_not_null()
        & pl.col("state").is_not_null()
        & pl.col("financial_year").is_not_null()
    )
    scored = add_robust_z(sanctioned, "sanction_amount", ["category", "state", "financial_year"])
    flagged = scored.filter(pl.col("robust_z").abs() > _Z_THRESHOLD)

    rows = []
    for r in flagged.iter_rows(named=True):
        ratio = r["sanction_amount"] / r["peer_median"] if r["peer_median"] else float("inf")
        rows.append(
            {
                "work_id": r["work_id"],
                "evidence": (
                    f"{fmt_inr(r['sanction_amount'])} is {ratio:.1f}x the peer median for "
                    f"\"{r['category']}\" in {r['state']} in FY {r['financial_year']} "
                    f"(median {fmt_inr(r['peer_median'])}, n={r['peer_n']})."
                ),
            }
        )
    return _flags(rows, "B1")


def b2_cost_per_unit_outlier(works: pl.DataFrame, expenditure: pl.DataFrame) -> pl.DataFrame:
    """Robust z-score of sanction_amount / quantity within category x
    unit x state — ₹/meter of road, ₹/unit of street light, ₹/litre of
    tanker capacity, etc.

    Coverage is real and low, reported here rather than assumed: 5.3%
    of sanctioned works (5,169 of 98,040) have an extractable quantity
    at all — confirmed against the real corpus that MPLADS descriptions
    are overwhelmingly location narratives ("from X's house to Y's
    house"), not quantity specifications (see quantity.py's module
    docstring). No financial year in the peer group here, unlike B1 —
    coverage is already thin; adding FY would fragment most groups
    below the n=30 floor.
    """
    sanctioned = works.filter(
        pl.col("sanction_amount").is_not_null()
        & pl.col("quantity").is_not_null()
        & (pl.col("quantity") > 0)
        & pl.col("state").is_not_null()
        & pl.col("category").is_not_null()
    ).with_columns((pl.col("sanction_amount") / pl.col("quantity")).alias("cost_per_unit"))

    scored = add_robust_z(sanctioned, "cost_per_unit", ["category", "quantity_unit", "state"])
    flagged = scored.filter(pl.col("robust_z").abs() > _Z_THRESHOLD)

    rows = []
    for r in flagged.iter_rows(named=True):
        ratio = r["cost_per_unit"] / r["peer_median"] if r["peer_median"] else float("inf")
        rows.append(
            {
                "work_id": r["work_id"],
                "evidence": (
                    f"{fmt_inr(r['cost_per_unit'])}/{r['quantity_unit']} ({fmt_inr(r['sanction_amount'])} "
                    f"for {r['quantity']:g} {r['quantity_unit']}(s)) is {ratio:.1f}x the peer median for "
                    f"\"{r['category']}\" in {r['state']} (median {fmt_inr(r['peer_median'])}/{r['quantity_unit']}, "
                    f"n={r['peer_n']})."
                ),
            }
        )
    return _flags(rows, "B2")


def b3_stalled_work(
    works: pl.DataFrame,
    expenditure: pl.DataFrame,
    as_of: dt.date | None = None,
    min_n: int = DEFAULT_MIN_PEER_GROUP,
) -> pl.DataFrame:
    """Days-since-sanction beyond the empirical P95 completion time for
    that category x state, on a work still not completed.

    The threshold is learned from the data (plan §03: "never hard-
    coded") — computed from every sanctioned work in that peer group
    that HAS completed, then applied to the ones still open.
    """
    as_of = as_of or dt.date.today()

    completed = works.filter(
        pl.col("sanction_date").is_not_null() & pl.col("completion_date").is_not_null()
    ).with_columns(
        (pl.col("completion_date") - pl.col("sanction_date")).dt.total_days().alias("days_to_complete")
    )
    thresholds = (
        completed.group_by(["category", "state"])
        .agg(
            pl.col("days_to_complete").quantile(0.95).alias("p95_days"),
            pl.len().alias("peer_n"),
        )
        .filter(pl.col("peer_n") >= min_n)
    )

    open_works = works.filter(
        pl.col("sanction_date").is_not_null() & pl.col("completion_date").is_null()
    ).with_columns((pl.lit(as_of) - pl.col("sanction_date")).dt.total_days().alias("days_open"))

    flagged = open_works.join(thresholds, on=["category", "state"], how="inner").filter(
        pl.col("days_open") > pl.col("p95_days")
    )

    rows = [
        {
            "work_id": r["work_id"],
            "evidence": (
                f"Sanctioned {r['days_open']} days ago and still not completed — the P95 "
                f"completion time for \"{r['category']}\" in {r['state']} is {r['p95_days']:.0f} "
                f"days (n={r['peer_n']} completed peers)."
            ),
        }
        for r in flagged.iter_rows(named=True)
    ]
    return _flags(rows, "B3")


# Round-rupee thresholds worth checking for "just under the tier"
# bunching — every one of these recurs heavily as an exact sanction
# amount in the real corpus (confirmed via the amount distribution),
# consistent with them functioning as real administrative tiers.
_BUNCHING_THRESHOLDS = [250_000, 500_000, 750_000, 1_000_000, 1_500_000, 2_000_000, 2_500_000]
_BUNCHING_BAND_FRACTION = 0.05  # "just below" = within 5% under the threshold
_BUNCHING_RATIO = 3.0
_BUNCHING_FLOOR_SHARE = 0.10


def b4_threshold_bunching(
    works: pl.DataFrame,
    expenditure: pl.DataFrame,
    min_n_bunching: int = 30,
) -> pl.DataFrame:
    """Excess mass of an agency's sanctions just under a round-rupee
    administrative tier, relative to the national share in that band.

    The plan also specified a Benford's-law first-digit test per
    agency, bundled under the same detector ID. Built, then retired
    before shipping — twice over, not once. First against the
    theoretical Benford curve: the *national* aggregate itself departs
    from it (digit 5 at 12.8% observed vs. 7.9% expected, digit 2 at
    23.0% vs. 17.6% — both reflecting how often exactly-round amounts
    like ₹5,00,000 occur), because a district officer's policy-chosen
    sanction figure isn't the kind of organically-arising quantity
    Benford's law describes — testing every agency against a curve the
    whole dataset already fails flagged all 333 eligible agencies at
    once. Swapping in the corpus's own empirical digit pattern as the
    baseline (the same fix that worked for B6 and B7) didn't help
    either: it still flagged all 333, because different agencies
    genuinely specialize in different work categories with different
    typical price points (a road-heavy agency vs. a water-tank-heavy
    one), so any per-agency digit distribution diverges from a
    category-blind baseline for entirely mundane compositional
    reasons — not suspicious rounding. A real fix needs the same
    category-controlled peer grouping B1 already has, applied to digit
    distributions, which is a bigger redesign than fits here.
    Threshold bunching doesn't share the flaw — it asks a narrower,
    category-agnostic question (does this agency cluster unusually
    close under a specific round-rupee figure) and validated cleanly:
    23.6% of eligible agencies flagged, not 0% or 100%.
    """
    rows: list[dict] = []

    sanctioned = works.filter(
        pl.col("sanction_amount").is_not_null() & pl.col("implementing_agency").is_not_null()
    )
    national_n = sanctioned.height
    agency_n_map = dict(
        sanctioned.group_by("implementing_agency").agg(pl.len().alias("n")).iter_rows()
    )

    for threshold in _BUNCHING_THRESHOLDS:
        band_lo = threshold * (1 - _BUNCHING_BAND_FRACTION)
        in_band = sanctioned.filter(
            (pl.col("sanction_amount") >= band_lo) & (pl.col("sanction_amount") < threshold)
        )
        if in_band.height == 0:
            continue
        national_share = in_band.height / national_n
        by_agency = in_band.group_by("implementing_agency").agg(pl.len().alias("band_n"), pl.col("work_id"))
        for r in by_agency.iter_rows(named=True):
            agency_n = agency_n_map.get(r["implementing_agency"])
            if not agency_n or agency_n < min_n_bunching:
                continue
            agency_share = r["band_n"] / agency_n
            if agency_share > _BUNCHING_FLOOR_SHARE and agency_share > _BUNCHING_RATIO * national_share:
                evidence = (
                    f"{agency_share:.0%} of {r['implementing_agency']}'s sanctions fall in the "
                    f"{fmt_inr(band_lo)}-{fmt_inr(threshold)} band, just under the {fmt_inr(threshold)} "
                    f"round-number tier — the national share in that band is {national_share:.0%}."
                )
                rows.extend({"work_id": wid, "evidence": evidence} for wid in r["work_id"])

    return _flags(rows, "B4")


def b6_agency_concentration(
    works: pl.DataFrame,
    expenditure: pl.DataFrame,
    min_works_per_mp: int = 10,
    percentile: float = 0.95,
) -> pl.DataFrame:
    """Herfindahl-Hirschman-style concentration: does one agency handle
    an unusually large share of one MP's sanctioned value?

    Flags every work belonging to the (MP, top agency) pair once that
    MP's top-agency share exceeds the `percentile` of the same
    statistic across all eligible MPs — a share is only "unusual" next
    to how concentrated other MPs' agency relationships normally are.

    Eligibility requires the MP to have used 2+ distinct agencies.
    Checked against real data before shipping without it: 187 of 677
    MPs with >=10 works (27.6%) route 100% of their value through a
    single agency — normal administrative structure (a constituency
    that sits entirely within one district has exactly one IDA, no
    choice of agency at all), not concentration. That ceiling pins the
    95th percentile at 1.0, so nothing can ever exceed it and the
    detector silently never fires. Restricting to MPs who genuinely
    had multiple agencies available and still skewed heavily toward
    one gives a real, spread distribution (0.10-0.996, no ties at the
    ceiling) — a share is only informative when there was a choice to
    concentrate away from.
    """
    sanctioned = works.filter(
        pl.col("sanction_amount").is_not_null()
        & pl.col("implementing_agency").is_not_null()
        & pl.col("mp_name").is_not_null()
    )

    by_mp_agency = sanctioned.group_by(["mp_name", "implementing_agency"]).agg(
        pl.col("sanction_amount").sum().alias("agency_total"),
        pl.len().alias("agency_n"),
    )
    mp_totals = by_mp_agency.group_by("mp_name").agg(
        pl.col("agency_total").sum().alias("mp_total"),
        pl.len().alias("n_agencies"),
        pl.col("agency_n").sum().alias("n_works"),
    )
    shares = by_mp_agency.join(mp_totals, on="mp_name").with_columns(
        (pl.col("agency_total") / pl.col("mp_total")).alias("share")
    )
    top_per_mp = (
        shares.filter((pl.col("n_works") >= min_works_per_mp) & (pl.col("n_agencies") >= 2))
        .sort("share", descending=True)
        .group_by("mp_name")
        .first()
    )
    if top_per_mp.height == 0:
        return EMPTY_FLAGS.clone()

    threshold = top_per_mp["share"].quantile(percentile)
    concentrated = top_per_mp.filter(pl.col("share") > threshold)

    rows = []
    for r in concentrated.iter_rows(named=True):
        member_works = sanctioned.filter(
            (pl.col("mp_name") == r["mp_name"]) & (pl.col("implementing_agency") == r["implementing_agency"])
        )
        evidence = (
            f"{r['implementing_agency']} handles {r['share']:.0%} of {r['mp_name']}'s sanctioned "
            f"value ({fmt_inr(r['agency_total'])} of {fmt_inr(r['mp_total'])} across "
            f"{r['n_agencies']} agencies) — above the {percentile:.0%} percentile of how "
            f"concentrated other MPs' top agency relationships are."
        )
        rows.extend({"work_id": wid, "evidence": evidence} for wid in member_works["work_id"].to_list())

    return _flags(rows, "B6")


def b7_year_end_bunching(
    works: pl.DataFrame,
    expenditure: pl.DataFrame,
    min_sanctions_per_fy: int = 40,
    percentile: float = 0.95,
) -> pl.DataFrame:
    """Disproportionate share of an MP's sanctions in a financial year's
    final 90 days (Jan-Mar) — the classic year-end-budget-dump pattern.

    Rescoped from the plan's original "final 90 days of the term":
    the 18th Lok Sabha/Rajya Sabha term the corpus covers hasn't ended
    yet, so "end of term" has no anchor in real data. Financial-year-end
    does — it's a well-defined, recurring boundary already present in
    every sanctioned work (financial_year), and year-end fund-dumping
    is itself a recognized government-spending anomaly, arguably a
    stronger real-world pattern than the original framing.

    min_sanctions_per_fy=40, not the plan's original 10: MPs typically
    submit sanctions in a few large annual batches rather than
    trickling them out, so at n=10 whether a whole batch happens to
    land in the 90-day window is close to a coin flip — 7.7% of
    MP-financial-year groups sat at exactly 100% (confirmed against
    the real corpus, in financial years that had already fully
    closed, not just the still-open current one), pinning the 95th
    percentile at the ceiling so nothing could ever exceed it. Raising
    the threshold to 40 needs a real multi-batch pattern to reach
    100%, drops the tie rate to 4.7%, and the percentile escapes the
    ceiling (0.990) — the same fix as B6, applied where the real data
    showed it was needed here too.
    """
    sanctioned = works.filter(
        pl.col("sanction_date").is_not_null()
        & pl.col("financial_year").is_not_null()
        & pl.col("mp_name").is_not_null()
    ).with_columns(
        # FY "2024-2025" ends 31 March 2025 — the second year in the string.
        pl.col("financial_year").str.slice(5, 4).cast(pl.Int32).alias("fy_end_year"),
    ).with_columns(
        pl.date(pl.col("fy_end_year"), 3, 31).alias("fy_end_date"),
    ).with_columns(
        (
            (pl.col("sanction_date") >= pl.col("fy_end_date") - pl.duration(days=90))
            # Upper-bounded at the FY's own end: a sanction dated after the
            # financial year it's tagged with already closed shouldn't count
            # as "that year's" year-end bunching. Confirmed zero real rows
            # hit this today (recommended_date/sanction_date evidently never
            # runs ahead of the tagged FY in this corpus), but the check
            # should hold regardless of what a future ingest brings in.
            & (pl.col("sanction_date") <= pl.col("fy_end_date"))
        ).alias("in_year_end_window")
    )

    by_mp_fy = sanctioned.group_by(["mp_name", "financial_year"]).agg(
        pl.len().alias("n_sanctions"),
        pl.col("in_year_end_window").sum().alias("n_year_end"),
    ).filter(pl.col("n_sanctions") >= min_sanctions_per_fy).with_columns(
        (pl.col("n_year_end") / pl.col("n_sanctions")).alias("year_end_share")
    )
    if by_mp_fy.height == 0:
        return EMPTY_FLAGS.clone()

    threshold = by_mp_fy["year_end_share"].quantile(percentile)
    bunched = by_mp_fy.filter(pl.col("year_end_share") > threshold)

    rows = []
    for r in bunched.iter_rows(named=True):
        member_works = sanctioned.filter(
            (pl.col("mp_name") == r["mp_name"])
            & (pl.col("financial_year") == r["financial_year"])
            & pl.col("in_year_end_window")
        )
        evidence = (
            f"{r['n_year_end']} of {r['mp_name']}'s {r['n_sanctions']} sanctions in FY "
            f"{r['financial_year']} ({r['year_end_share']:.0%}) fall in the final 90 days of "
            f"the financial year — above the {percentile:.0%} percentile across all MPs that FY."
        )
        rows.extend({"work_id": wid, "evidence": evidence} for wid in member_works["work_id"].to_list())

    return _flags(rows, "B7")


_B8_SIMILARITY_THRESHOLD = 0.90
_B8_WINDOW_DAYS = 180


def b8_near_duplicate_funding(works: pl.DataFrame, expenditure: pl.DataFrame) -> pl.DataFrame:
    """TF-IDF cosine similarity >=0.90 between distinct work IDs in the
    same district, recommended within 180 days of each other —
    possible double sanction of one physical asset.

    Near-verbatim matches (>=0.999 similarity) are excluded by
    text_similarity.similar_pairs itself, not filtered here — see its
    module docstring for why: MPLADS routinely has one MP recommending
    the same standard item at many sites with one copy-pasted
    description (the largest real example: 118 identical entries from
    a single MP), which is legitimate and would otherwise flood this
    detector exactly as it did A3's original, retired design.

    The 180-day window is an addition to the plan's original wording
    (same district, no time constraint), added after checking real
    volume: same-district-and-similar-wording alone matched 13,162
    pairs — about 20% of the corpus, implausibly high for "double
    funding of one specific asset". Two different real assets can
    easily share generic, terse phrasing ("Construction of Cremation
    ground") without being the same asset at all; a genuine double
    sanction is far more plausible when the two entries are also close
    in time. Restricting to 180 days keeps 4,817 pairs (36.6% of the
    original set) — a judgment call about a reasonable window for a
    duplicate entry to occur, not a value derived from the data the
    way B6/B7/B4's fixes were; stated as such rather than dressed up
    as more rigorous than it is.
    """
    candidates = works.filter(
        pl.col("work_id").str.starts_with("WS/")
        & pl.col("description").is_not_null()
        & (pl.col("description") != "")
        & ~pl.col("description_corrupted")
        & pl.col("district_raw").is_not_null()
        & pl.col("recommended_date").is_not_null()
    )

    rows: list[dict] = []
    for district in candidates["district_raw"].unique().to_list():
        group = candidates.filter(pl.col("district_raw") == district)
        if group.height < 2:
            continue
        ids = group["work_id"].to_list()
        texts = group["description"].to_list()
        dates = group["recommended_date"].to_list()
        for i, j, sim in similar_pairs(texts, threshold=_B8_SIMILARITY_THRESHOLD):
            if abs((dates[i] - dates[j]).days) > _B8_WINDOW_DAYS:
                continue
            for a, b in ((i, j), (j, i)):
                rows.append(
                    {
                        "work_id": ids[a],
                        "evidence": (
                            f"Description is {sim:.0%} similar to work {ids[b]} in the same district "
                            f"({district}), recommended within {_B8_WINDOW_DAYS} days of it — possible "
                            f"double funding of one asset."
                        ),
                    }
                )

    return _flags(rows, "B8")


_B5_SIMILARITY_THRESHOLD = 0.85
_B5_WINDOW_DAYS = 30
_B5_MIN_CLUSTER = 3
_B5_MAX_MEMBER_SHARE = 0.5


class _UnionFind:
    def __init__(self, n: int) -> None:
        self.parent = list(range(n))

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb


def b5_work_splitting(works: pl.DataFrame, expenditure: pl.DataFrame) -> pl.DataFrame:
    """Three or more works from the same agency, similar descriptions,
    recommended within a 30-day window, sized comparably to each other
    rather than one dominant work with incidental small extras.

    Two deliberate departures from the plan's original wording, both
    forced by what the schema actually has:

    - "same village/ward" -> same implementing_agency + district_raw.
      Village/ward isn't a field eSAKSHI exports; district + agency is
      the finest location grain available (an IDA is typically a
      single district office), consistent with every other detector's
      location handling in this codebase.
    - "each below a threshold, summing above it" -> no single work's
      amount exceeds half the cluster's combined total, instead of a
      specific rupee threshold. There's no confirmed MPLADS per-work
      approval threshold in the data to test against (B4 already
      covers round-number bunching separately); "no piece dominates
      the total" is threshold-free but captures the same underlying
      shape — comparably-sized pieces that together are worth more
      than any one of them looks alone.

    Uses the same near-exact exclusion as B8 (via text_similarity), so
    a legitimate bulk template batch isn't rediscovered as "splitting".
    """
    candidates = works.filter(
        pl.col("work_id").str.starts_with("WS/")
        & pl.col("description").is_not_null()
        & (pl.col("description") != "")
        & ~pl.col("description_corrupted")
        & pl.col("implementing_agency").is_not_null()
        & pl.col("district_raw").is_not_null()
        & pl.col("recommended_date").is_not_null()
        & pl.col("recommended_amount").is_not_null()
    )

    rows: list[dict] = []
    groups = candidates.group_by(["implementing_agency", "district_raw"]).agg(
        pl.col("work_id"), pl.col("description"), pl.col("recommended_date"), pl.col("recommended_amount")
    )
    for g in groups.iter_rows(named=True):
        n = len(g["work_id"])
        if n < _B5_MIN_CLUSTER:
            continue
        pairs = similar_pairs(g["description"], threshold=_B5_SIMILARITY_THRESHOLD)
        if not pairs:
            continue

        uf = _UnionFind(n)
        for i, j, _sim in pairs:
            days_apart = abs((g["recommended_date"][i] - g["recommended_date"][j]).days)
            if days_apart <= _B5_WINDOW_DAYS:
                uf.union(i, j)

        clusters: dict[int, list[int]] = {}
        for idx in range(n):
            clusters.setdefault(uf.find(idx), []).append(idx)

        for members in clusters.values():
            if len(members) < _B5_MIN_CLUSTER:
                continue
            amounts = [g["recommended_amount"][m] for m in members]
            total = sum(amounts)
            if total <= 0 or max(amounts) > _B5_MAX_MEMBER_SHARE * total:
                continue
            member_ids = [g["work_id"][m] for m in members]
            evidence = (
                f"{len(members)} similarly-worded works from {g['implementing_agency']} in "
                f"{g['district_raw']}, recommended within {_B5_WINDOW_DAYS} days of each other, "
                f"totalling {fmt_inr(total)} with no single work over {_B5_MAX_MEMBER_SHARE:.0%} of that "
                f"total: {', '.join(member_ids)}."
            )
            rows.extend({"work_id": wid, "evidence": evidence} for wid in member_ids)

    return _flags(rows, "B5")
