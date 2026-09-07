from pathlib import Path

from parakh.overrides import (
    add_override,
    get_override,
    list_overrides,
    overridden_work_ids,
    remove_override,
)


def test_add_and_get_override(tmp_path: Path):
    db = tmp_path / "overrides.sqlite"
    add_override("WS/MP1/2024-2025/1", "Terrain-driven cost, checked against site report.", db_path=db)

    result = get_override("WS/MP1/2024-2025/1", db_path=db)
    assert result is not None
    assert result["work_id"] == "WS/MP1/2024-2025/1"
    assert result["note"] == "Terrain-driven cost, checked against site report."
    assert result["reviewed_at"]


def test_get_override_missing_returns_none(tmp_path: Path):
    db = tmp_path / "overrides.sqlite"
    assert get_override("WS/MP1/2024-2025/1", db_path=db) is None


def test_add_override_upserts(tmp_path: Path):
    db = tmp_path / "overrides.sqlite"
    add_override("WS/MP1/2024-2025/1", "First note.", db_path=db)
    add_override("WS/MP1/2024-2025/1", "Revised note.", db_path=db)

    assert len(list_overrides(db_path=db)) == 1
    assert get_override("WS/MP1/2024-2025/1", db_path=db)["note"] == "Revised note."


def test_remove_override(tmp_path: Path):
    db = tmp_path / "overrides.sqlite"
    add_override("WS/MP1/2024-2025/1", None, db_path=db)

    assert remove_override("WS/MP1/2024-2025/1", db_path=db) is True
    assert get_override("WS/MP1/2024-2025/1", db_path=db) is None


def test_remove_override_missing_returns_false(tmp_path: Path):
    db = tmp_path / "overrides.sqlite"
    assert remove_override("WS/MP1/2024-2025/1", db_path=db) is False


def test_overridden_work_ids(tmp_path: Path):
    db = tmp_path / "overrides.sqlite"
    add_override("WS/MP1/2024-2025/1", None, db_path=db)
    add_override("WS/MP2/2024-2025/2", None, db_path=db)

    assert overridden_work_ids(db_path=db) == {"WS/MP1/2024-2025/1", "WS/MP2/2024-2025/2"}
