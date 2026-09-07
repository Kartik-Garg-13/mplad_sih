"""build_database() must never leave the API with no database to serve.

The original implementation deleted parakh.duckdb and rebuilt it in place —
any failure between that delete and a successful close (bad data reaching a
detector, a training error, the process being killed mid-build) permanently
destroyed the corpus, recoverable only by a manual CLI rebuild. These tests
run the real function against a copy of the actual build inputs and force a
failure partway through, so the guarantee is checked against real behavior,
not a mock of it.
"""

from __future__ import annotations

import shutil

import duckdb
import pytest

from parakh import database
from parakh.config import PROCESSED_DIR


@pytest.fixture
def db_snapshot():
    """Back up the real parakh.duckdb and any in-progress temp file, restore
    both after the test — this suite runs against the actual processed data,
    the same way test_pipeline.py and test_uploads.py do."""
    backup = PROCESSED_DIR / "parakh.duckdb.test-backup"
    shutil.copy2(database.DB_PATH, backup)
    try:
        yield
    finally:
        database._TMP_DB_PATH.unlink(missing_ok=True)
        shutil.move(str(backup), str(database.DB_PATH))


def _n_works() -> int:
    con = duckdb.connect(str(database.DB_PATH), read_only=True)
    try:
        return con.execute("SELECT count(*) FROM works").fetchone()[0]
    finally:
        con.close()


def test_a_failed_build_leaves_the_existing_database_untouched(db_snapshot, monkeypatch):
    before = _n_works()

    def _boom(*_args, **_kwargs):
        raise RuntimeError("simulated failure mid-build")

    # Fails after the temp file is created and tables are being written, but
    # before the atomic swap — exactly the window the old code had no
    # protection for.
    monkeypatch.setattr(database, "train_and_evaluate", _boom)

    with pytest.raises(RuntimeError, match="simulated failure"):
        database.build_database()

    assert database.DB_PATH.exists(), "the old, working database must still be there"
    assert _n_works() == before, "untouched — not partially overwritten"
    assert not database._TMP_DB_PATH.exists(), "the failed temp build must be cleaned up, not left behind"


def test_a_successful_build_replaces_the_database(db_snapshot):
    database.build_database()
    assert database.DB_PATH.exists()
    assert not database._TMP_DB_PATH.exists()
    assert _n_works() > 0
