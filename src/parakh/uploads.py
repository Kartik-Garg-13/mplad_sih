"""Register a user-supplied set of eSAKSHI exports as a new source batch.

config.py's docstring promises that a further term is added by adding a
HOUSE_TERMS entry, not by editing parsers. That is exactly what this does,
at runtime: an upload lands in data/raw/<key>/ under the filenames the
registry records, and from then on the ordinary ingest path treats it like
any other house/term.

Validation runs the real loaders rather than a column checklist. A CSV can
satisfy every name we would think to check and still break on the composite
Work field or a date format, so the only honest test of "will the pipeline
accept this" is putting it through the pipeline's own front door.
"""

from __future__ import annotations

import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

import polars as pl

from parakh import config
from parakh.config import UNPARSEABLE_WORK_ID, UNSANCTIONED_WORK_ID

# What each export unlocks, shown on the upload page so a partial batch is an
# informed choice rather than a silent degradation.
STAGE_INFO: dict[str, dict[str, str]] = {
    "recommended": {
        "label": "Works Recommended",
        "example": "Works Recommended.csv",
        "unlocks": "The spine — every work starts here. Without it a batch contributes nothing.",
    },
    "sanctioned": {
        "label": "Works Sanctioned",
        "example": "Works Sanctioned.csv",
        "unlocks": "Sanction amounts and work status. Needed for B1, B3, B4, B6 and B7.",
    },
    "completed": {
        "label": "Works Completed",
        "example": "Works Completed.csv",
        "unlocks": "Completion dates and photo-evidence metadata. Needed for A5 and B3.",
    },
    "expenditure": {
        "label": "Expenditure on Completed and On-going Works",
        "example": "Expenditure on Completed and On-going Works as on Date.csv",
        "unlocks": "Transaction-level payments. Needed for A1, A2 and the vendor graph.",
    },
    "allocated": {
        "label": "Allocated Limit for Hon'ble MPs",
        "example": "Allocated Limit for Honble MPs.csv",
        "unlocks": "Per-MP entitlement. Feeds the constituency fund-utilisation view.",
    },
    "calamity": {
        "label": "Amount consented for Calamity",
        "example": "Amount consented for Calamity.csv",
        "unlocks": "Calamity consents. Kept in the canonical layer for context.",
    },
}

_SLUG_RE = re.compile(r"[^a-z0-9]+")
MAX_UPLOAD_BYTES = 200 * 1024 * 1024


class UploadError(ValueError):
    """A batch the pipeline would not be able to read."""


def slugify(label: str) -> str:
    slug = _SLUG_RE.sub("_", label.strip().lower()).strip("_")
    return slug or "batch"


def make_key(label: str) -> str:
    """A registry key that collides with neither a built-in nor an existing batch."""
    base = f"upload_{slugify(label)}"[:60]
    taken = set(config.house_terms())
    key = base
    n = 2
    while key in taken:
        key = f"{base}_{n}"
        n += 1
    return key


def batch_dir(key: str) -> Path:
    return config.RAW_DIR / key


def list_batches() -> list[dict]:
    return config.load_upload_registry()


def _check_no_id_overlap(new_work_ids: pl.Series) -> None:
    """Refuse a batch whose real work IDs already exist in the corpus.

    Every detector, and every peer-group statistic Tier B computes, assumes
    one row per real-world work. Re-uploading the same export twice (or any
    batch that overlaps an existing source) duplicates those rows under a
    new house_key instead: confirmed live during testing that a 59-row
    overlapping upload alone produced 502 spurious A1 flags and 59 spurious
    A3 flags — detectors that fire zero times on the clean corpus — because
    every payment and every work_id was being counted twice.

    The two work-ID sentinels (not-yet-sanctioned, unparseable) are excluded
    — thousands of genuine rows legitimately share each literal sentinel
    string, so that's not a real collision, just two different works that
    both happen to have no real ID yet.
    """
    works_path = config.PROCESSED_DIR / "works.parquet"
    if not works_path.exists():
        return  # nothing built yet to overlap with

    real_new = new_work_ids.filter(
        (new_work_ids != UNSANCTIONED_WORK_ID) & (new_work_ids != UNPARSEABLE_WORK_ID)
    ).unique()
    if real_new.is_empty():
        return

    existing = pl.scan_parquet(works_path).select("work_id").collect()["work_id"]
    overlap = real_new.filter(real_new.is_in(existing.implode()))
    if overlap.is_empty():
        return

    sample = ", ".join(overlap.to_list()[:5])
    raise UploadError(
        f"{overlap.len()} work ID(s) in this batch already exist in the corpus "
        f"(e.g. {sample}) — adding it would double-count those works in every "
        "detector and peer-group statistic. If this is meant to replace an "
        "existing source rather than add to it, remove that source first."
    )


def _validate(key: str) -> dict[str, int]:
    """Run the real loaders over a staged batch. Returns per-stage row counts.

    Raises UploadError with the loader's own complaint attached — a missing
    column surfaces as the column name the parser wanted, which is far more
    actionable than "invalid CSV".
    """
    from parakh import ingest

    counts: dict[str, int] = {}
    for stage in config.STAGES:
        if ingest.stage_path(key, stage) is None:
            continue
        try:
            frame = ingest.STAGE_LOADERS[stage](key)
        except Exception as exc:  # noqa: BLE001 — surfaced verbatim to the user
            label = STAGE_INFO[stage]["label"]
            raise UploadError(
                f"{label}: this file does not look like an eSAKSHI {label} export "
                f"({type(exc).__name__}: {exc})"
            ) from exc
        counts[stage] = frame.height
        if stage == "recommended":
            _check_no_id_overlap(frame["work_id"])
    return counts


def create_batch(
    label: str,
    house: str,
    term: str,
    files: dict[str, tuple[str, bytes]],
    note: str | None = None,
) -> dict:
    """Stage, validate, and register an upload. Rolls back on any failure."""
    label = (label or "").strip()
    if not label:
        raise UploadError("Give the batch a name so it can be told apart later.")

    missing = [s for s in config.REQUIRED_STAGES if s not in files]
    if missing:
        names = ", ".join(STAGE_INFO[s]["label"] for s in missing)
        raise UploadError(f"{names} is required — the works table is built from it.")

    unknown = set(files) - set(config.STAGES)
    if unknown:
        raise UploadError(f"Unrecognised dataset slot(s): {', '.join(sorted(unknown))}")

    total = sum(len(blob) for _, blob in files.values())
    if total > MAX_UPLOAD_BYTES:
        raise UploadError(
            f"Batch is {total / 1e6:.0f} MB; the limit is {MAX_UPLOAD_BYTES / 1e6:.0f} MB."
        )

    key = make_key(label)
    target = batch_dir(key)
    if target.exists():
        raise UploadError(f"A batch directory already exists at {target.name}.")

    registry_names: dict[str, str] = {}
    try:
        target.mkdir(parents=True)
        for stage, (filename, blob) in files.items():
            # The registry records the name we wrote, not the browser's, so a
            # re-download suffix like " 1" or a renamed file can never
            # desynchronise the registry from what is on disk.
            safe = f"{stage}.csv"
            (target / safe).write_bytes(blob)
            registry_names[stage] = safe
            del filename

        batch = {
            "key": key,
            "label": label,
            "house": (house or "").strip() or label,
            "term": (term or "").strip() or "—",
            "note": (note or "").strip() or None,
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "files": registry_names,
        }
        # Register before validating: the loaders resolve paths through the
        # registry, so the batch has to be visible to config for the dry run.
        config.save_upload_registry([*config.load_upload_registry(), batch])

        try:
            batch["row_counts"] = _validate(key)
        except Exception:
            config.save_upload_registry(
                [b for b in config.load_upload_registry() if b.get("key") != key]
            )
            raise

        registered = config.load_upload_registry()
        for entry in registered:
            if entry.get("key") == key:
                entry["row_counts"] = batch["row_counts"]
        config.save_upload_registry(registered)
        return batch
    except Exception:
        shutil.rmtree(target, ignore_errors=True)
        raise


def delete_batch(key: str) -> bool:
    """Unregister a batch and delete its raw files. Built-ins are refused."""
    if config.is_builtin(key):
        raise UploadError("The built-in eSAKSHI exports cannot be removed.")
    remaining = [b for b in config.load_upload_registry() if b.get("key") != key]
    if len(remaining) == len(config.load_upload_registry()):
        return False
    config.save_upload_registry(remaining)
    shutil.rmtree(batch_dir(key), ignore_errors=True)
    return True
