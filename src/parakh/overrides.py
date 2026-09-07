"""Reviewer overrides — plan §08, rule 7: "reviewed, explained" state.

Deliberately not a table in parakh.duckdb: that database is read-only
at API time and gets fully unlinked and rebuilt from scratch by every
`python -m parakh.database` run (see database.py), which would silently
wipe every reviewer's work. Overrides live in a separate, small SQLite
file that a database rebuild never touches.

A reviewer marking a flag "reviewed — explained" doesn't delete the
flag or the evidence — it records that a human looked and found the
benign explanation credible for this specific work. The flag list uses
this to suppress (not destroy) reviewed works by default (plan §08:
overrides must be visible and reversible, not a silent delete).
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from parakh.config import PROCESSED_DIR

DB_PATH = PROCESSED_DIR / "overrides.sqlite"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS overrides (
    work_id TEXT PRIMARY KEY,
    note TEXT,
    reviewed_at TEXT NOT NULL
)
"""


@contextmanager
def _connect(db_path: Path = DB_PATH):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db_path))
    try:
        con.execute(_SCHEMA)
        yield con
        con.commit()
    finally:
        con.close()


def add_override(work_id: str, note: str | None, db_path: Path = DB_PATH) -> dict:
    reviewed_at = datetime.now(timezone.utc).isoformat()
    with _connect(db_path) as con:
        con.execute(
            "INSERT INTO overrides (work_id, note, reviewed_at) VALUES (?, ?, ?) "
            "ON CONFLICT(work_id) DO UPDATE SET note = excluded.note, reviewed_at = excluded.reviewed_at",
            (work_id, note, reviewed_at),
        )
    return {"work_id": work_id, "note": note, "reviewed_at": reviewed_at}


def remove_override(work_id: str, db_path: Path = DB_PATH) -> bool:
    with _connect(db_path) as con:
        cur = con.execute("DELETE FROM overrides WHERE work_id = ?", (work_id,))
        return cur.rowcount > 0


def get_override(work_id: str, db_path: Path = DB_PATH) -> dict | None:
    with _connect(db_path) as con:
        row = con.execute(
            "SELECT work_id, note, reviewed_at FROM overrides WHERE work_id = ?", (work_id,)
        ).fetchone()
    if row is None:
        return None
    return {"work_id": row[0], "note": row[1], "reviewed_at": row[2]}


def list_overrides(db_path: Path = DB_PATH) -> list[dict]:
    with _connect(db_path) as con:
        rows = con.execute(
            "SELECT work_id, note, reviewed_at FROM overrides ORDER BY reviewed_at DESC"
        ).fetchall()
    return [{"work_id": r[0], "note": r[1], "reviewed_at": r[2]} for r in rows]


def overridden_work_ids(db_path: Path = DB_PATH) -> set[str]:
    with _connect(db_path) as con:
        rows = con.execute("SELECT work_id FROM overrides").fetchall()
    return {r[0] for r in rows}
