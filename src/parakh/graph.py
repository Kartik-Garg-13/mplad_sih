"""E2 — the agency network. Bipartite MP<->agency and agency<->vendor
graphs, centrality, Louvain communities, and two agency-level anomaly
signals.

Two departures from the plan, both forced by checking real data before
shipping, in the same spirit as every Tier B correction:

- "agency <-> district" was dropped entirely: an implementing agency's
  name embeds its district ("DISTRICT PLANNING OFFICER PATNA_IDA"), so
  agency-district is 1:1 by construction — confirmed against the real
  corpus, zero agencies span more than one district. There is no graph
  here to draw.
- "agencies reaching abnormally many unrelated constituencies" was
  retired as an anomaly signal, not built with a lower threshold. The
  agencies with the most distinct MPs are exactly the ones you'd
  expect — Kannur, Kottayam, Palakkad, Bangalore Urban — big-population
  district administrations that legitimately span several constituencies.
  MP-count correlates with work volume at r=0.44 and the top of the
  list is mundane; shipping it would read as not understanding the
  domain, the opposite of what this flag is supposed to demonstrate.

What's real instead: the vendor-name dataset the plan expected to need
dataful.in for is already in expenditure.parquet (28,162 distinct
vendors, 30,337 agency-vendor pairs) — no external source needed. And
agency names that appear under more than one state (19 real cases) are
a genuine, specific, small anomaly list — most likely a data-entry
inconsistency rather than two different agencies sharing a name, but
worth a look either way.
"""

from __future__ import annotations

import networkx as nx
import polars as pl

# Below this many works, an agency's total value is compared against
# what "normal-sized" agencies earn per work — a handful of works
# carrying a lot of money is the thin-file shape worth a look.
_THIN_FILE_MAX_WORKS = 5
_THIN_FILE_RATIO = 3.0


def build_mp_agency_edges(works: pl.DataFrame) -> pl.DataFrame:
    sanctioned = works.filter(
        pl.col("sanction_amount").is_not_null()
        & pl.col("implementing_agency").is_not_null()
        & pl.col("mp_name").is_not_null()
    )
    return sanctioned.group_by(["mp_name", "implementing_agency"]).agg(
        pl.len().alias("n_works"),
        pl.col("sanction_amount").sum().alias("total_value"),
    )


def build_agency_vendor_edges(expenditure: pl.DataFrame) -> pl.DataFrame:
    paid = expenditure.filter(
        pl.col("vendor_name").is_not_null()
        & pl.col("implementing_agency").is_not_null()
        & (pl.col("vendor_name") != "")
    )
    return paid.group_by(["implementing_agency", "vendor_name"]).agg(
        pl.len().alias("n_payments"),
        pl.col("amount").sum().alias("total_value"),
    )


def _mp_agency_graph(edges: pl.DataFrame) -> nx.Graph:
    g = nx.Graph()
    for r in edges.iter_rows(named=True):
        mp_node, agency_node = f"mp:{r['mp_name']}", f"agency:{r['implementing_agency']}"
        g.add_node(mp_node, kind="mp", label=r["mp_name"])
        g.add_node(agency_node, kind="agency", label=r["implementing_agency"])
        g.add_edge(mp_node, agency_node, weight=r["total_value"], n_works=r["n_works"])
    return g


def compute_communities(edges: pl.DataFrame) -> pl.DataFrame:
    """Louvain communities over the value-weighted MP<->agency graph."""
    g = _mp_agency_graph(edges)
    if g.number_of_edges() == 0:
        return pl.DataFrame(schema={"node": pl.Utf8, "kind": pl.Utf8, "label": pl.Utf8, "community": pl.Int64})
    communities = nx.algorithms.community.louvain_communities(g, weight="weight", seed=42)
    rows = [
        {"node": node, "kind": g.nodes[node]["kind"], "label": g.nodes[node]["label"], "community": i}
        for i, members in enumerate(communities)
        for node in members
    ]
    return pl.DataFrame(rows)


def compute_agency_metrics(works: pl.DataFrame) -> pl.DataFrame:
    sanctioned = works.filter(
        pl.col("sanction_amount").is_not_null() & pl.col("implementing_agency").is_not_null()
    )
    overall_median_work_value = sanctioned["sanction_amount"].median()

    metrics = sanctioned.group_by("implementing_agency").agg(
        pl.len().alias("n_works"),
        pl.col("sanction_amount").sum().alias("total_value"),
        pl.col("mp_name").n_unique().alias("n_mps"),
        pl.col("state").n_unique().alias("n_states"),
        pl.col("state").unique().alias("states"),
    )
    metrics = metrics.with_columns(
        (pl.col("total_value") / pl.col("n_works")).alias("value_per_work"),
        (pl.col("n_states") > 1).alias("is_cross_state"),
    )
    metrics = metrics.with_columns(
        (
            (pl.col("n_works") <= _THIN_FILE_MAX_WORKS)
            & (pl.col("value_per_work") > _THIN_FILE_RATIO * overall_median_work_value)
        ).alias("is_thin_file")
    )
    return metrics
