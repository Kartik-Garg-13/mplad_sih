"""Read-only API over parakh.duckdb — the whole point of the batch
architecture (plan §02): every endpoint here is a SELECT, nothing
computes a detector live. Run with:

    uvicorn parakh.api.main:app --reload --port 8000
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import math
import threading
from contextlib import asynccontextmanager
from typing import Any

import duckdb
from fastapi import Body, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from parakh import config, rebuild, uploads
from parakh import detectors as detector_registry
from parakh.database import DB_PATH
from parakh.detector_meta import DETECTORS
from parakh.peer_distributions import group_key as peer_group_key
from parakh import overrides as overrides_store

_con: duckdb.DuckDBPyConnection | None = None
# Guards the _con handle itself, not query execution — a rebuild has to be
# certain no request is mid-`.cursor()` while it closes the connection.
_con_lock = threading.RLock()


def get_con() -> duckdb.DuckDBPyConnection:
    """A fresh cursor per call, not the shared connection object.

    Each FastAPI request handler runs in its own threadpool thread
    (plain `def` endpoints are dispatched via run_in_threadpool), and a
    single DuckDBPyConnection isn't safe to use concurrently from
    multiple threads — confirmed the hard way: Promise.all() firing
    /api/flags, /api/meta and /api/stats at once from the frontend
    produced intermittent `fetchone()` returning None mid-query.
    `.cursor()` gives each request an independent handle onto the same
    open database, safe for exactly this concurrent-request pattern.
    """
    with _con_lock:
        if _con is None:
            # Only reachable while a rebuild has the database closed.
            raise HTTPException(
                status_code=503,
                detail="The corpus is being rebuilt — this takes under a minute.",
            )
        return _con.cursor()


def _close_db() -> None:
    """Release the file so database.py can delete and recreate it.

    On Windows, unlinking a file another handle still holds fails outright,
    so this is not optional bookkeeping — skip it and the rebuild dies with
    a PermissionError partway through.
    """
    global _con
    with _con_lock:
        if _con is not None:
            _con.close()
            _con = None


def _open_db() -> None:
    global _con
    with _con_lock:
        if _con is None and DB_PATH.exists():
            _con = duckdb.connect(str(DB_PATH), read_only=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _con
    if not DB_PATH.exists():
        raise RuntimeError(f"{DB_PATH} does not exist — run `python -m parakh.database` first")
    _open_db()
    yield
    _close_db()


app = FastAPI(title="PARAKH API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3010"],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)

_WORK_SUMMARY_COLS = [
    "work_id", "state", "district_raw", "implementing_agency", "mp_name",
    "category", "description", "sanction_amount", "recommended_amount",
    "work_status", "financial_year",
]


def _rows_to_dicts(cur: duckdb.DuckDBPyConnection, sql: str, params: list | None = None) -> list[dict[str, Any]]:
    result = cur.execute(sql, params or [])
    cols = [d[0] for d in result.description]
    return [dict(zip(cols, row)) for row in result.fetchall()]


@app.get("/api/stats")
def get_stats() -> dict:
    con = get_con()
    n_works = con.execute("SELECT count(*) FROM works").fetchone()[0]
    n_flags = con.execute("SELECT count(*) FROM flags").fetchone()[0]
    n_flagged = con.execute("SELECT count(*) FROM work_flag_summary").fetchone()[0]
    by_detector = _rows_to_dicts(
        con, "SELECT detector, tier, count(*) AS n FROM flags GROUP BY detector, tier ORDER BY detector"
    )
    return {
        "total_works": n_works,
        "total_flags": n_flags,
        "flagged_works": n_flagged,
        "flagged_share": round(n_flagged / n_works, 4) if n_works else 0,
        "by_detector": by_detector,
        # The true count of registered detectors — not len(by_detector),
        # which only lists detectors that fired at least once on this
        # corpus (A1/A3 can legitimately sit at zero flags on a clean
        # dataset while still being real, implemented detectors).
        "n_detectors": len(detector_registry.REGISTRY),
    }


@app.get("/api/overview")
def get_overview() -> dict:
    """Aggregates for the /dashboard page — every number here is a plain
    GROUP BY over `works`/`work_flag_summary`, same read-only pattern as
    every other endpoint. No new computation, no new table.
    """
    con = get_con()

    by_state = _rows_to_dicts(
        con,
        """
        SELECT w.state, count(*) AS n_flagged
        FROM work_flag_summary s JOIN works w ON w.work_id = s.work_id
        WHERE w.state IS NOT NULL
        GROUP BY 1 ORDER BY n_flagged DESC LIMIT 12
        """,
    )
    by_year = _rows_to_dicts(
        con,
        """
        SELECT w.financial_year, count(*) AS n_works,
               count(s.work_id) AS n_flagged
        FROM works w LEFT JOIN work_flag_summary s ON w.work_id = s.work_id
        WHERE w.financial_year IS NOT NULL
        GROUP BY 1 ORDER BY 1
        """,
    )
    by_category = _rows_to_dicts(
        con,
        """
        SELECT w.category, count(*) AS n_flagged
        FROM work_flag_summary s JOIN works w ON w.work_id = s.work_id
        WHERE w.category IS NOT NULL
        GROUP BY 1 ORDER BY n_flagged DESC LIMIT 8
        """,
    )
    tier_composition = _rows_to_dicts(
        con,
        """
        SELECT
            CASE WHEN has_tier_a AND has_tier_b THEN 'both'
                 WHEN has_tier_a THEN 'tier_a_only'
                 ELSE 'tier_b_only' END AS bucket,
            count(*) AS n
        FROM work_flag_summary GROUP BY 1
        """,
    )

    return {
        "by_state": by_state,
        "by_year": by_year,
        "by_category": by_category,
        "tier_composition": tier_composition,
    }


@app.get("/api/search")
def search(q: str = Query(..., min_length=2)) -> dict:
    """Fans a single query out across works, agencies and constituencies —
    unifies the three per-page `search` filters that already existed
    independently on /flags, /agencies and /constituencies.

    Each category returns a `LIMIT 8` preview plus its own true `count(*)`
    — the preview is deliberately small (this is a header search box, not
    a results page), but the count is not: showing "8 matches" for a query
    that actually has thousands would understate the corpus by orders of
    magnitude, exactly the kind of overclaim-by-omission this project's
    own vocabulary lock exists to catch on the wording side. The frontend
    uses the count to say "showing 8 of N" and link to the full filtered
    list each of those pages already supports.
    """
    con = get_con()
    needle = f"%{q}%"

    works_where = "description ILIKE ? OR mp_name ILIKE ? OR implementing_agency ILIKE ? OR work_id ILIKE ?"
    works_params = [needle, needle, needle, needle]
    works = _rows_to_dicts(
        con,
        f"""
        SELECT work_id, description, state, mp_name, implementing_agency, sanction_amount
        FROM works WHERE {works_where} LIMIT 8
        """,
        works_params,
    )
    n_works = con.execute(f"SELECT count(*) FROM works WHERE {works_where}", works_params).fetchone()[0]

    agencies_where = "implementing_agency ILIKE ?"
    agencies_params = [needle]
    agencies = _rows_to_dicts(
        con,
        f"SELECT implementing_agency, n_works, total_value FROM agency_metrics WHERE {agencies_where} LIMIT 8",
        agencies_params,
    )
    n_agencies = con.execute(
        f"SELECT count(*) FROM agency_metrics WHERE {agencies_where}", agencies_params
    ).fetchone()[0]

    constituencies_where = "constituency ILIKE ? OR mp_name ILIKE ?"
    constituencies_params = [needle, needle]
    constituencies = _rows_to_dicts(
        con,
        f"""
        SELECT state, constituency, mp_name, n_sanctioned
        FROM constituency_scorecard WHERE {constituencies_where} LIMIT 8
        """,
        constituencies_params,
    )
    n_constituencies = con.execute(
        f"SELECT count(*) FROM constituency_scorecard WHERE {constituencies_where}", constituencies_params
    ).fetchone()[0]

    return {
        "query": q,
        "works": works,
        "n_works": n_works,
        "agencies": agencies,
        "n_agencies": n_agencies,
        "constituencies": constituencies,
        "n_constituencies": n_constituencies,
    }


@app.get("/api/validation")
def get_validation() -> dict:
    """Plan §07's four detector-validation methods (a fifth, the stall
    model's time-split PR-AUC/calibration, is already served by
    /api/model/stall-risk) — computed by `python -m parakh.validation.build`,
    read here exactly as stored, nothing computed live.
    """
    con = get_con()
    synthetic_per_type = _rows_to_dicts(con, "SELECT * FROM validation_synthetic_per_type")
    synthetic_at_k = _rows_to_dicts(con, "SELECT * FROM validation_synthetic_at_k ORDER BY k")
    stability = _rows_to_dicts(con, "SELECT * FROM validation_stability ORDER BY detector")
    known_cases = _rows_to_dicts(con, "SELECT * FROM validation_known_cases")
    adjudication_clusters = _rows_to_dicts(
        con, "SELECT * FROM validation_adjudication_clusters ORDER BY n_works_in_top50 DESC"
    )
    return {
        "synthetic_injection": {"per_type": synthetic_per_type, "at_k": synthetic_at_k},
        "stability": stability,
        "known_cases": known_cases,
        "adjudication": {
            "clusters": adjudication_clusters,
            "n_reviewed": sum(c["n_works_in_top50"] for c in adjudication_clusters),
        },
    }


@app.get("/api/provenance")
def get_provenance() -> dict:
    con = get_con()
    rows = _rows_to_dicts(con, "SELECT * FROM provenance")
    if not rows:
        raise HTTPException(status_code=404, detail="Provenance record not found")
    return rows[0]


@app.get("/api/meta")
def get_meta() -> dict:
    con = get_con()
    states = [r[0] for r in con.execute(
        "SELECT DISTINCT state FROM works WHERE state IS NOT NULL ORDER BY state"
    ).fetchall()]
    categories = [r[0] for r in con.execute(
        "SELECT DISTINCT category FROM works WHERE category IS NOT NULL ORDER BY category"
    ).fetchall()]
    detectors = [r[0] for r in con.execute(
        "SELECT DISTINCT detector FROM flags ORDER BY detector"
    ).fetchall()]
    return {"states": states, "categories": categories, "detectors": detectors}


@app.get("/api/detectors")
def list_detector_meta() -> dict:
    """The 13 registered detectors — title, description, and benign
    explanation — served from `detector_meta.py`, the single copy of this
    text (plan §08, rule 3: shown by default, not behind a click). Static,
    not read from the database — this describes the detector *code*, not
    this build's data, so it needs no rebuild to stay correct.
    """
    return {
        "detectors": [
            {
                "id": d.id,
                "tier": d.tier,
                "title": d.title,
                "description": d.description,
                "benign_explanation": d.benign_explanation,
            }
            for d in DETECTORS.values()
        ]
    }


def _flags_where_clause(
    *,
    detector: str | None,
    tier: str | None,
    state: str | None,
    category: str | None,
    search: str | None,
    source: str | None,
    include_reviewed: bool,
) -> tuple[str, list]:
    """The `/api/flags` filter set, extracted so the CSV export below
    applies exactly the same filters as the queue a reviewer is actually
    looking at — a export that silently used different criteria than the
    screen it was downloaded from would be worse than no export at all.
    """
    where = ["1=1"]
    params: list = []

    if not include_reviewed:
        reviewed_ids = overrides_store.overridden_work_ids()
        if reviewed_ids:
            # One bound list parameter, not one placeholder per override —
            # the previous query text grew with every reviewer action ever
            # taken, which both re-plans a longer SQL string on every single
            # /api/flags call and has no real ceiling as override activity
            # accumulates.
            where.append("NOT (w.work_id = ANY(?))")
            params.append(list(reviewed_ids))
    if detector:
        where.append("s.detectors @> [?]")
        params.append(detector)
    if tier == "A":
        where.append("s.has_tier_a")
    elif tier == "B":
        where.append("s.has_tier_b")
    if state:
        where.append("w.state = ?")
        params.append(state)
    if category:
        where.append("w.category = ?")
        params.append(category)
    if search:
        where.append("(w.description ILIKE ? OR w.mp_name ILIKE ? OR w.implementing_agency ILIKE ?)")
        needle = f"%{search}%"
        params += [needle, needle, needle]
    if source:
        where.append("w.house_key = ?")
        params.append(source)

    return " AND ".join(where), params


@app.get("/api/flags")
def list_flagged_works(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    detector: str | None = None,
    tier: str | None = Query(None, pattern="^[AB]$"),
    state: str | None = None,
    category: str | None = None,
    search: str | None = None,
    source: str | None = None,
    include_reviewed: bool = False,
) -> dict:
    """`include_reviewed=false` (the default) hides works a reviewer has
    marked "reviewed — explained" from the queue — suppressed, not
    deleted (plan §08, rule 7): the flag and its evidence stay on the
    work detail page and in the database either way.
    """
    con = get_con()
    where_clause, params = _flags_where_clause(
        detector=detector, tier=tier, state=state, category=category,
        search=search, source=source, include_reviewed=include_reviewed,
    )

    total = con.execute(
        f"SELECT count(*) FROM work_flag_summary s JOIN works w ON w.work_id = s.work_id WHERE {where_clause}",
        params,
    ).fetchone()[0]

    offset = (page - 1) * page_size
    cols = ", ".join(f"w.{c}" for c in _WORK_SUMMARY_COLS)
    rows = _rows_to_dicts(
        con,
        f"""
        SELECT {cols}, s.n_flags, s.detectors, s.has_tier_a, s.has_tier_b
        FROM work_flag_summary s
        JOIN works w ON w.work_id = s.work_id
        WHERE {where_clause}
        ORDER BY s.has_tier_a DESC, s.n_flags DESC, w.work_id
        LIMIT ? OFFSET ?
        """,
        params + [page_size, offset],
    )

    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": math.ceil(total / page_size) if page_size else 0,
        "results": rows,
    }


@app.get("/api/unflagged")
def list_unflagged_works(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    state: str | None = None,
    category: str | None = None,
    search: str | None = None,
    source: str | None = None,
    include_unsanctioned: bool = False,
) -> dict:
    """The flip side of `/api/flags`: every work with zero flags at all —
    a `LEFT JOIN ... WHERE s.work_id IS NULL` against `work_flag_summary`,
    not a filter on it, since a work with no row there is exactly what
    "no flags" means. No detector/tier/include_reviewed params — none of
    those have meaning for a work no detector ever touched.

    `include_unsanctioned=false` (the default) is the honest reading of
    "no flags": measured against the real corpus, 33,397 of the 93,736
    works with no flags have no sanction amount at all — the
    not-yet-sanctioned placeholder rows (see config.UNSANCTIONED_WORK_ID)
    that nearly every detector skips by construction, since they filter
    on `sanction_amount is not null` first. Counting those as "clean"
    would conflate "was evaluated and came back clear" (60,339 works)
    with "was never evaluated at all", which is exactly the kind of
    overstatement this project's evidence rules exist to prevent. The
    toggle exposes them rather than hiding them; it just doesn't lead
    with them.
    """
    con = get_con()

    where = ["s.work_id IS NULL"]
    params: list = []
    if not include_unsanctioned:
        where.append("w.sanction_amount IS NOT NULL")
    if state:
        where.append("w.state = ?")
        params.append(state)
    if category:
        where.append("w.category = ?")
        params.append(category)
    if search:
        where.append("(w.description ILIKE ? OR w.mp_name ILIKE ? OR w.implementing_agency ILIKE ?)")
        needle = f"%{search}%"
        params += [needle, needle, needle]
    if source:
        where.append("w.house_key = ?")
        params.append(source)
    where_clause = " AND ".join(where)

    total = con.execute(
        f"SELECT count(*) FROM works w LEFT JOIN work_flag_summary s ON w.work_id = s.work_id WHERE {where_clause}",
        params,
    ).fetchone()[0]

    offset = (page - 1) * page_size
    cols = ", ".join(f"w.{c}" for c in _WORK_SUMMARY_COLS)
    rows = _rows_to_dicts(
        con,
        f"""
        SELECT {cols}
        FROM works w
        LEFT JOIN work_flag_summary s ON w.work_id = s.work_id
        WHERE {where_clause}
        ORDER BY w.work_id
        LIMIT ? OFFSET ?
        """,
        params + [page_size, offset],
    )

    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": math.ceil(total / page_size) if page_size else 0,
        "results": rows,
    }


@app.get("/api/flags/export.csv")
def export_flags_csv(
    detector: str | None = None,
    tier: str | None = Query(None, pattern="^[AB]$"),
    state: str | None = None,
    category: str | None = None,
    search: str | None = None,
    source: str | None = None,
    include_reviewed: bool = False,
) -> Response:
    """CSV of every flag on every work matching the current `/flags`
    filters — not just the one page on screen. Every flag's evidence
    carries its detector's benign explanation in the same row, so the
    restraint travels with the data instead of being stripped on the one
    path data actually leaves the tool.

    One row per (work, flag): the top-level filters (tier, detector, ...)
    select which *works* are in scope exactly as `/api/flags` does, but
    every matching work's flags across both tiers are included — narrowing
    to only the flags that happen to match the filter would silently drop
    a work's other evidence, the same information-stripping this endpoint
    exists to avoid.
    """
    con = get_con()
    where_clause, params = _flags_where_clause(
        detector=detector, tier=tier, state=state, category=category,
        search=search, source=source, include_reviewed=include_reviewed,
    )
    work_cols = ", ".join(f"w.{c}" for c in _WORK_SUMMARY_COLS)
    rows = _rows_to_dicts(
        con,
        f"""
        SELECT {work_cols}, f.detector, f.tier, f.evidence
        FROM work_flag_summary s
        JOIN works w ON w.work_id = s.work_id
        JOIN flags f ON f.work_id = w.work_id
        WHERE {where_clause}
        ORDER BY w.work_id, f.tier, f.detector
        """,
        params,
    )

    buf = io.StringIO()
    fieldnames = [*_WORK_SUMMARY_COLS, "detector", "tier", "evidence", "benign_explanation"]
    writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for r in rows:
        meta = DETECTORS.get(r["detector"])
        writer.writerow({**r, "benign_explanation": meta.benign_explanation if meta else ""})

    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="parakh-flags.csv"'},
    )


def _bucket_index(value: float, edges: list[float]) -> int:
    """Which histogram bucket `value` falls into, using the same half-open
    binning `numpy.histogram` used to build `bucket_counts` in the first
    place (peer_distributions.py) — the two have to agree, or a work's own
    marker would land in a bucket its own count wasn't added to."""
    n_buckets = len(edges) - 1
    if value <= edges[0]:
        return 0
    if value >= edges[-1]:
        return n_buckets - 1
    for i in range(n_buckets):
        if edges[i] <= value < edges[i + 1]:
            return i
    return n_buckets - 1


@app.get("/api/works/{work_id:path}/peers")
def get_work_peers(work_id: str) -> dict:
    """B1/B3 peer-group histograms for this work, with its own value's
    bucket marked — what turns Tier B's prose ("4.2x the peer median,
    n=151") into something a reviewer can actually see rather than just
    read. Precomputed in `peer_distributions` at build time (see
    database.py); this endpoint only looks the work's group up and places
    a marker, the same "nothing computes a detector live" guarantee every
    other endpoint here holds.

    A work with no eligible peer group for a given detector (its own
    category/state/financial-year group never reached the n>=30 floor)
    simply has no entry for that detector — the same abstention Tier B
    itself applies, not an error.
    """
    con = get_con()
    rows = _rows_to_dicts(
        con,
        "SELECT category, state, financial_year, sanction_amount, sanction_date, completion_date "
        "FROM works WHERE work_id = ?",
        [work_id],
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Work not found")
    work = rows[0]
    peers: dict[str, dict] = {}

    if work["category"] and work["state"] and work["financial_year"] and work["sanction_amount"] is not None:
        key = peer_group_key(work["category"], work["state"], work["financial_year"])
        dist_rows = _rows_to_dicts(
            con,
            "SELECT n, median, bucket_edges, bucket_counts FROM peer_distributions "
            "WHERE detector = 'B1' AND group_key = ?",
            [key],
        )
        if dist_rows:
            dist = dist_rows[0]
            peers["B1"] = {
                **dist,
                "own_value": work["sanction_amount"],
                "own_bucket": _bucket_index(work["sanction_amount"], dist["bucket_edges"]),
            }

    if work["category"] and work["state"] and work["sanction_date"]:
        # A completed work shows where it actually landed; an open work
        # shows its current days-open against the same completed-peer
        # distribution B3 itself compares it to — which is the entire
        # point of a B3 flag (it only ever fires on open works), so this
        # is not an approximation, it is what the detector is doing.
        if work["completion_date"]:
            own_days = (work["completion_date"] - work["sanction_date"]).days
        else:
            own_days = (dt.date.today() - work["sanction_date"]).days
        key = peer_group_key(work["category"], work["state"])
        dist_rows = _rows_to_dicts(
            con,
            "SELECT n, median, bucket_edges, bucket_counts FROM peer_distributions "
            "WHERE detector = 'B3' AND group_key = ?",
            [key],
        )
        if dist_rows:
            dist = dist_rows[0]
            peers["B3"] = {
                **dist,
                "own_value": own_days,
                "own_bucket": _bucket_index(own_days, dist["bucket_edges"]),
            }

    return {"work_id": work_id, "peers": peers}


# Registered after /peers, not before: both are GET routes sharing the
# `/api/works/{work_id:path}` prefix, and Starlette's `path` converter is
# greedy — the first matching GET route wins, so a broader
# `/api/works/{work_id:path}` registered first would swallow "/peers" as
# part of work_id and this endpoint would 404 forever. Confirmed live: it
# did, until this got reordered.
@app.get("/api/works/{work_id:path}")
def get_work_detail(work_id: str) -> dict:
    con = get_con()
    work_rows = _rows_to_dicts(con, "SELECT * FROM works WHERE work_id = ?", [work_id])
    if not work_rows:
        raise HTTPException(status_code=404, detail="Work not found")
    work = work_rows[0]

    flags = _rows_to_dicts(
        con,
        "SELECT detector, tier, evidence FROM flags WHERE work_id = ? ORDER BY tier, detector",
        [work_id],
    )
    payments = _rows_to_dicts(
        con,
        """
        SELECT expenditure_date, vendor_name, payment_status, amount
        FROM expenditure WHERE work_id = ? ORDER BY expenditure_date
        """,
        [work_id],
    )

    return {"work": work, "flags": flags, "payments": payments, "override": overrides_store.get_override(work_id)}


@app.post("/api/works/{work_id:path}/override")
def create_override(work_id: str, note: str | None = Body(None, embed=True)) -> dict:
    con = get_con()
    exists = con.execute("SELECT 1 FROM works WHERE work_id = ?", [work_id]).fetchone()
    if not exists:
        raise HTTPException(status_code=404, detail="Work not found")
    return overrides_store.add_override(work_id, note)


@app.delete("/api/works/{work_id:path}/override")
def delete_override(work_id: str) -> dict:
    removed = overrides_store.remove_override(work_id)
    if not removed:
        raise HTTPException(status_code=404, detail="No override on file for this work")
    return {"work_id": work_id, "removed": True}


@app.get("/api/overrides")
def list_overrides(search: str | None = None) -> dict:
    """Every work marked "reviewed — explained" — the other half of plan
    §08, rule 7 that was never wired up: `overrides.list_overrides()` has
    existed since the override feature shipped, but nothing ever called
    it, so a reviewer had no way to see what they — or anyone — had
    already reviewed. Joined against `works` here so the list is readable
    (a work ID alone means nothing); an override whose work has since
    disappeared from the corpus (a source removed, see uploads.py) is
    still listed; its work fields come back null rather than dropping the
    override silently.

    `search` filters by the same fields every other list page's search
    box matches (description, MP, agency) — applied in Python against the
    already-joined rows rather than a second SQL round-trip, since the
    override count this filters over is inherently small (one person's
    review history, not the 131K-work corpus /api/flags searches).
    """
    con = get_con()
    rows = overrides_store.list_overrides()
    if not rows:
        return {"overrides": []}

    work_ids = [r["work_id"] for r in rows]
    cols = ", ".join(_WORK_SUMMARY_COLS)
    work_rows = _rows_to_dicts(
        con, f"SELECT {cols} FROM works WHERE work_id = ANY(?)", [work_ids]
    )
    works_by_id = {w["work_id"]: w for w in work_rows}

    overrides = [{**r, "work": works_by_id.get(r["work_id"])} for r in rows]

    if search:
        needle = search.lower()

        def _matches(entry: dict) -> bool:
            work = entry.get("work") or {}
            fields = (work.get("description"), work.get("mp_name"), work.get("implementing_agency"))
            return any(f and needle in f.lower() for f in fields)

        overrides = [o for o in overrides if _matches(o)]

    return {"overrides": overrides}


@app.get("/api/agencies")
def list_agencies(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    thin_file: bool | None = None,
    cross_state: bool | None = None,
    search: str | None = None,
    sort: str = Query("total_value", pattern="^(total_value|n_works|n_mps|value_per_work)$"),
) -> dict:
    con = get_con()

    where = ["1=1"]
    params: list = []
    if thin_file is not None:
        where.append("is_thin_file = ?")
        params.append(thin_file)
    if cross_state is not None:
        where.append("is_cross_state = ?")
        params.append(cross_state)
    if search:
        where.append("implementing_agency ILIKE ?")
        params.append(f"%{search}%")
    where_clause = " AND ".join(where)

    total = con.execute(f"SELECT count(*) FROM agency_metrics WHERE {where_clause}", params).fetchone()[0]
    offset = (page - 1) * page_size
    rows = _rows_to_dicts(
        con,
        f"""
        SELECT implementing_agency, n_works, total_value, n_mps, n_states,
               value_per_work, is_thin_file, is_cross_state
        FROM agency_metrics
        WHERE {where_clause}
        ORDER BY {sort} DESC
        LIMIT ? OFFSET ?
        """,
        params + [page_size, offset],
    )
    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": math.ceil(total / page_size) if page_size else 0,
        "results": rows,
    }


@app.get("/api/agencies/{agency:path}")
def get_agency_detail(agency: str) -> dict:
    con = get_con()
    metrics_rows = _rows_to_dicts(con, "SELECT * FROM agency_metrics WHERE implementing_agency = ?", [agency])
    if not metrics_rows:
        raise HTTPException(status_code=404, detail="Agency not found")
    metrics = metrics_rows[0]

    community_rows = con.execute(
        "SELECT community FROM communities WHERE label = ? AND kind = 'agency'", [agency]
    ).fetchall()
    metrics["community"] = community_rows[0][0] if community_rows else None

    mps = _rows_to_dicts(
        con,
        """
        SELECT mp_name, n_works, total_value FROM mp_agency_edges
        WHERE implementing_agency = ? ORDER BY total_value DESC
        """,
        [agency],
    )
    vendors = _rows_to_dicts(
        con,
        """
        SELECT vendor_name, n_payments, total_value FROM agency_vendor_edges
        WHERE implementing_agency = ? ORDER BY total_value DESC LIMIT 50
        """,
        [agency],
    )
    states = _rows_to_dicts(
        con,
        "SELECT DISTINCT state FROM works WHERE implementing_agency = ? AND state IS NOT NULL",
        [agency],
    )

    return {
        "agency": metrics,
        "states": [s["state"] for s in states],
        "mps": mps,
        "vendors": vendors,
    }


@app.get("/api/graph/mp-agency")
def get_mp_agency_graph(min_value: float = Query(0, ge=0)) -> dict:
    """Full bipartite MP<->agency graph as nodes + edges, for Cytoscape.

    `min_value` prunes low-value edges client-side isn't asked to
    render — the full unfiltered graph is ~1,470 nodes / 2,481 edges,
    perfectly renderable, but a value floor lets the UI offer a
    decluttered default view.
    """
    con = get_con()
    edges = _rows_to_dicts(
        con,
        """
        SELECT mp_name, implementing_agency, n_works, total_value
        FROM mp_agency_edges WHERE total_value >= ?
        """,
        [min_value],
    )
    communities = _rows_to_dicts(con, "SELECT node, kind, label, community FROM communities")
    community_by_node = {c["node"]: c["community"] for c in communities}

    nodes: dict[str, dict] = {}
    for e in edges:
        mp_node, agency_node = f"mp:{e['mp_name']}", f"agency:{e['implementing_agency']}"
        if mp_node not in nodes:
            nodes[mp_node] = {"id": mp_node, "kind": "mp", "label": e["mp_name"], "community": community_by_node.get(mp_node)}
        if agency_node not in nodes:
            nodes[agency_node] = {
                "id": agency_node,
                "kind": "agency",
                "label": e["implementing_agency"],
                "community": community_by_node.get(agency_node),
            }

    edge_list = [
        {
            "source": f"mp:{e['mp_name']}",
            "target": f"agency:{e['implementing_agency']}",
            "n_works": e["n_works"],
            "total_value": e["total_value"],
        }
        for e in edges
    ]
    return {"nodes": list(nodes.values()), "edges": edge_list}


@app.get("/api/model/stall-risk")
def get_stall_model_metrics() -> dict:
    con = get_con()
    rows = _rows_to_dicts(con, "SELECT * FROM model_metrics")
    if not rows:
        raise HTTPException(status_code=404, detail="Model metrics not found")
    metrics = rows[0]
    importances = _rows_to_dicts(con, "SELECT feature, importance FROM feature_importances ORDER BY importance DESC")
    return {"metrics": metrics, "feature_importances": importances}


@app.get("/api/at-risk")
def list_at_risk_works(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    state: str | None = None,
    category: str | None = None,
    search: str | None = None,
) -> dict:
    con = get_con()

    where = ["1=1"]
    params: list = []
    if state:
        where.append("state = ?")
        params.append(state)
    if category:
        where.append("category = ?")
        params.append(category)
    if search:
        where.append("(description ILIKE ? OR mp_name ILIKE ? OR implementing_agency ILIKE ?)")
        needle = f"%{search}%"
        params += [needle, needle, needle]
    where_clause = " AND ".join(where)

    total = con.execute(f"SELECT count(*) FROM at_risk WHERE {where_clause}", params).fetchone()[0]
    offset = (page - 1) * page_size
    rows = _rows_to_dicts(
        con,
        f"""
        SELECT work_id, stall_risk, days_open, p75_days, state, district_raw,
               implementing_agency, mp_name, category, description, sanction_amount
        FROM at_risk
        WHERE {where_clause}
        ORDER BY stall_risk DESC
        LIMIT ? OFFSET ?
        """,
        params + [page_size, offset],
    )
    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": math.ceil(total / page_size) if page_size else 0,
        "results": rows,
    }


@app.get("/api/constituencies")
def list_constituencies(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    state: str | None = None,
    search: str | None = None,
    sort: str = Query(
        "total_sanctioned",
        pattern="^(completion_rate|fund_utilisation|unspent_balance|total_sanctioned|n_sanctioned)$",
    ),
    direction: str = Query("desc", pattern="^(asc|desc)$"),
) -> dict:
    """Lok Sabha only — Rajya Sabha members have no constituency (§01).
    No choropleth here and no population-normalised rate either; see
    constituency.py's module docstring for why both were left out
    rather than faked."""
    con = get_con()

    where = ["1=1"]
    params: list = []
    if state:
        where.append("state = ?")
        params.append(state)
    if search:
        where.append("(constituency ILIKE ? OR mp_name ILIKE ?)")
        needle = f"%{search}%"
        params += [needle, needle]
    where_clause = " AND ".join(where)

    total = con.execute(f"SELECT count(*) FROM constituency_scorecard WHERE {where_clause}", params).fetchone()[0]
    offset = (page - 1) * page_size
    order_dir = "ASC NULLS LAST" if direction == "asc" else "DESC NULLS LAST"
    rows = _rows_to_dicts(
        con,
        f"""
        SELECT state, constituency, mp_name, n_sanctioned, n_completed, completion_rate,
               median_days_to_complete, total_sanctioned, total_expended, allocated_amount,
               fund_utilisation, unspent_balance, dominant_category, dominant_category_share
        FROM constituency_scorecard
        WHERE {where_clause}
        ORDER BY {sort} {order_dir}
        LIMIT ? OFFSET ?
        """,
        params + [page_size, offset],
    )
    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": math.ceil(total / page_size) if page_size else 0,
        "results": rows,
    }


# --- Datasets ---------------------------------------------------------------
# Adding a batch is the one operation that writes to the corpus. It cannot be
# a plain SELECT like everything else above, and it cannot score the new rows
# on their own either: 8 of the 13 detectors are peer-relative and need the
# whole corpus for comparison. So an upload stages files, then triggers the
# same full rebuild that `python -m parakh.pipeline && python -m parakh.database`
# would run — reported back through a job the UI polls.


def _source_counts(con: duckdb.DuckDBPyConnection) -> dict[str, dict]:
    rows = _rows_to_dicts(
        con,
        """
        SELECT w.house_key,
               count(*) AS n_works,
               count(s.work_id) AS n_flagged
        FROM works w
        LEFT JOIN work_flag_summary s ON w.work_id = s.work_id
        GROUP BY 1
        """,
    )
    return {r["house_key"]: r for r in rows}


@app.get("/api/datasets")
def list_datasets() -> dict:
    """Every source in the corpus — the built-in exports and any uploads."""
    counts: dict[str, dict] = {}
    if not rebuild.is_rebuilding():
        try:
            counts = _source_counts(get_con())
        except HTTPException:
            counts = {}

    sources = []
    for key in config.HOUSE_TERMS:
        c = counts.get(key, {})
        sources.append({
            "key": key,
            "label": f"{config.house_of(key)} ({config.term_of(key)} term)",
            "house": config.house_of(key),
            "term": config.term_of(key),
            "builtin": True,
            "created_at": None,
            "note": None,
            "files": config.FILES[key],
            "n_works": c.get("n_works", 0),
            "n_flagged": c.get("n_flagged", 0),
        })
    for batch in uploads.list_batches():
        c = counts.get(batch["key"], {})
        sources.append({
            "key": batch["key"],
            "label": batch.get("label") or batch["key"],
            "house": batch.get("house"),
            "term": batch.get("term"),
            "builtin": False,
            "created_at": batch.get("created_at"),
            "note": batch.get("note"),
            "files": batch.get("files", {}),
            "row_counts": batch.get("row_counts", {}),
            "n_works": c.get("n_works", 0),
            "n_flagged": c.get("n_flagged", 0),
        })

    job = rebuild.current_job()
    return {
        "sources": sources,
        "stages": [
            {"key": k, **v, "required": k in config.REQUIRED_STAGES}
            for k, v in uploads.STAGE_INFO.items()
        ],
        "rebuild": job.as_dict() if job else None,
    }


_UPLOAD_CHUNK_BYTES = 1024 * 1024  # 1 MiB


async def _read_capped(upload: UploadFile, budget: int) -> bytes:
    """Read an upload in chunks, aborting the moment the running total
    across this and any earlier file in the same request would exceed
    `budget` — the previous version called `upload.read()` (no size limit)
    per file and only checked the combined size after every file had
    already been fully buffered, so a batch well over the limit was read
    entirely into memory before ever being rejected.
    """
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await upload.read(_UPLOAD_CHUNK_BYTES)
        if not chunk:
            break
        total += len(chunk)
        if total > budget:
            raise HTTPException(
                status_code=413,
                detail=f"Batch exceeds the {uploads.MAX_UPLOAD_BYTES / 1e6:.0f} MB limit.",
            )
        chunks.append(chunk)
    return b"".join(chunks)


@app.post("/api/datasets")
async def create_dataset(
    label: str = Form(...),
    house: str = Form(""),
    term: str = Form(""),
    note: str = Form(""),
    recommended: UploadFile | None = File(None),
    sanctioned: UploadFile | None = File(None),
    completed: UploadFile | None = File(None),
    expenditure: UploadFile | None = File(None),
    allocated: UploadFile | None = File(None),
    calamity: UploadFile | None = File(None),
) -> dict:
    if rebuild.is_rebuilding():
        raise HTTPException(status_code=409, detail="A rebuild is already running — wait for it to finish.")

    incoming = {
        "recommended": recommended,
        "sanctioned": sanctioned,
        "completed": completed,
        "expenditure": expenditure,
        "allocated": allocated,
        "calamity": calamity,
    }
    files: dict[str, tuple[str, bytes]] = {}
    remaining_budget = uploads.MAX_UPLOAD_BYTES
    for stage, upload in incoming.items():
        if upload is None or not upload.filename:
            continue
        blob = await _read_capped(upload, remaining_budget)
        remaining_budget -= len(blob)
        files[stage] = (upload.filename, blob)

    try:
        batch = uploads.create_batch(label=label, house=house, term=term, files=files, note=note)
    except uploads.UploadError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    try:
        job = rebuild.start_rebuild(f"Adding “{batch['label']}”", _close_db, _open_db)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return {"batch": batch, "job": job.as_dict()}


@app.delete("/api/datasets/{key}")
def delete_dataset(key: str) -> dict:
    if rebuild.is_rebuilding():
        raise HTTPException(status_code=409, detail="A rebuild is already running — wait for it to finish.")
    try:
        removed = uploads.delete_batch(key)
    except uploads.UploadError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not removed:
        raise HTTPException(status_code=404, detail="No such dataset")

    job = rebuild.start_rebuild(f"Removing “{key}”", _close_db, _open_db)
    return {"removed": key, "job": job.as_dict()}


@app.get("/api/datasets/jobs/{job_id}")
def get_rebuild_job(job_id: str) -> dict:
    job = rebuild.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="No such job")
    return job.as_dict()
