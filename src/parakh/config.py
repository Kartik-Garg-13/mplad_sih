"""Paths and constants for the eSAKSHI 18th-term raw exports.

Raw files are the citizen-export CSVs pulled by hand from
mplads.mospi.gov.in (no login, no scraper — see docs/data_sources.md).
Nothing here should need to change if a later term's exports are added;
add a new HOUSE_TERMS entry instead of editing the parsers.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = REPO_ROOT / "data" / "raw"
PROCESSED_DIR = REPO_ROOT / "data" / "processed"

# One entry per (house, term) we have raw exports for. Extending to the
# 17th Lok Sabha or Rajya Sabha-earlier just means adding a key here,
# pointing at a new data/raw/<dir> with the same six filenames.
HOUSE_TERMS: dict[str, Path] = {
    "lok_sabha_18": RAW_DIR / "esakshi_ls_18ls",
    "rajya_sabha_18": RAW_DIR / "esakshi_rs_18ls",
}

# Filenames are the literal names eSAKSHI's export button produces.
# The Lok Sabha directory's files carry a trailing " 1" (the browser's
# own de-dupe suffix on a second download) — kept as-is rather than
# renamed, so raw/ stays a faithful copy of what was downloaded.
FILES = {
    "lok_sabha_18": {
        "allocated": "Allocated Limit for Honble MPs 1.csv",
        "calamity": "Amount consented for Calamity 1.csv",
        "recommended": "Works Recommended 1.csv",
        "sanctioned": "Works Sanctioned 1.csv",
        "completed": "Works Completed 1.csv",
        "expenditure": "Expenditure on Completed and On-going Works as on Date 1.csv",
    },
    "rajya_sabha_18": {
        "allocated": "Allocated Limit for Honble MPs.csv",
        "calamity": "Amount consented for Calamity.csv",
        "recommended": "Works Recommended.csv",
        "sanctioned": "Works Sanctioned.csv",
        "completed": "Works Completed.csv",
        "expenditure": "Expenditure on Completed and On-going Works as on Date.csv",
    },
}

HOUSE_OF = {
    "lok_sabha_18": "Lok Sabha",
    "rajya_sabha_18": "Rajya Sabha",
}
TERM_OF = {
    "lok_sabha_18": "18th",
    "rajya_sabha_18": "18th",
}

# --- Uploaded batches -------------------------------------------------------
# The module docstring above promises that a later term is added by adding a
# HOUSE_TERMS entry, not by editing parsers. Uploads take exactly that route,
# at runtime instead of in source: each registered batch is a directory under
# data/raw/ holding the same eSAKSHI exports under this registry's recorded
# filenames, and every accessor below merges those batches into what the
# ingest layer sees.
#
# The registry deliberately lives outside parakh.duckdb — database.py deletes
# and recreates that file on every rebuild, so a batch recorded inside it
# would erase itself the moment its own ingestion ran. Same reasoning as
# overrides.sqlite.

STAGES = (
    "recommended",
    "sanctioned",
    "completed",
    "expenditure",
    "allocated",
    "calamity",
)

# "Works Recommended" is the spine: build_works_table() starts from it and
# left-joins the rest, so a batch without it contributes no works at all.
# Every other stage enriches and may be absent.
REQUIRED_STAGES = ("recommended",)

UPLOAD_REGISTRY_PATH = PROCESSED_DIR / "uploads.json"


def load_upload_registry() -> list[dict]:
    """Registered upload batches, oldest first. Never raises.

    A malformed or half-written registry degrades to "no uploads" rather than
    taking the whole API down with it — the built-in corpus must always
    still load.
    """
    if not UPLOAD_REGISTRY_PATH.exists():
        return []
    try:
        data = json.loads(UPLOAD_REGISTRY_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    batches = data.get("batches", [])
    return batches if isinstance(batches, list) else []


def save_upload_registry(batches: list[dict]) -> None:
    UPLOAD_REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    UPLOAD_REGISTRY_PATH.write_text(
        json.dumps({"batches": batches}, indent=2), encoding="utf-8"
    )


def _batch(house_key: str) -> dict | None:
    for batch in load_upload_registry():
        if batch.get("key") == house_key:
            return batch
    return None


def house_terms() -> dict[str, Path]:
    """Built-in house/terms plus every registered upload batch."""
    merged: dict[str, Path] = dict(HOUSE_TERMS)
    for batch in load_upload_registry():
        merged[batch["key"]] = RAW_DIR / batch["key"]
    return merged


def files_for(house_key: str) -> dict[str, str]:
    if house_key in FILES:
        return FILES[house_key]
    batch = _batch(house_key)
    if batch is None:
        raise KeyError(f"Unknown house/term or upload batch: {house_key!r}")
    return batch.get("files", {})


def house_of(house_key: str) -> str:
    if house_key in HOUSE_OF:
        return HOUSE_OF[house_key]
    batch = _batch(house_key)
    if batch is None:
        raise KeyError(f"Unknown house/term or upload batch: {house_key!r}")
    return batch.get("house") or batch.get("label") or house_key


def term_of(house_key: str) -> str:
    if house_key in TERM_OF:
        return TERM_OF[house_key]
    batch = _batch(house_key)
    if batch is None:
        raise KeyError(f"Unknown house/term or upload batch: {house_key!r}")
    return batch.get("term") or "—"


def is_builtin(house_key: str) -> bool:
    return house_key in HOUSE_TERMS


# The real observed Work Status pipeline (confirmed in recon, not assumed).
# Order matters for B3 (stalled work) — a work "further along" this list
# is closer to done.
WORK_STATUS_STAGES = [
    "Sanction",
    "Time Estimation",
    "Vendor Identification",
    "Physical Inspection",
    "Work partially Completed",
    "Work Completed",
]

# Footer row every eSAKSHI export ends with.
GRAND_TOTAL_MARKER = "Grand Total"

# Two distinct sentinels, deliberately not one. Confirmed in recon:
# a literal "NA" work ID has 100% correlation with an empty Sanction
# Date — eSAKSHI only allots a real work ID once a district authority
# sanctions the work, so "NA" means "recommended, not yet sanctioned",
# not "corrupted". A row that matches neither the ID pattern nor that
# literal "NA" placeholder is the genuinely unparseable case.
UNSANCTIONED_WORK_ID = "NOT_YET_SANCTIONED"
UNPARSEABLE_WORK_ID = "UNPARSEABLE"
