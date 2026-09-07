"""Re-run the batch pipeline in-process, while the API is serving.

Adding a source batch means rebuilding everything: 8 of the 13 detectors
are peer-relative (B1/B2 need a >=30-work peer group, B3 learns a P95
threshold from completed works, B4/B6/B7 compare against all-MP
percentiles), so newly uploaded rows cannot be scored on their own. They
have to go through the same full run as the built-in corpus, which is
cheap enough to do live — the whole thing takes well under a minute.

The awkward part is that database.build_database() deletes and recreates
parakh.duckdb while the API holds it open. On Windows that unlink fails
outright rather than orphaning the handle, so the connection has to be
closed first and reopened after. The API passes those two callbacks in,
and every read endpoint reports 503 in between rather than reading a file
that is being rewritten underneath it.
"""

from __future__ import annotations

import threading
import traceback
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone

STEPS = (
    "Reading the raw exports into canonical tables",
    "Running the 13 detectors, graph and stall model",
    "Rebuilding the validation tables",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Job:
    id: str
    reason: str
    status: str = "running"  # running | done | error
    step: int = 0
    step_label: str = STEPS[0]
    total_steps: int = len(STEPS)
    error: str | None = None
    started_at: str = field(default_factory=_now)
    finished_at: str | None = None

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "reason": self.reason,
            "status": self.status,
            "step": self.step,
            "step_label": self.step_label,
            "total_steps": self.total_steps,
            "error": self.error,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


_jobs: dict[str, Job] = {}
_current: Job | None = None
_lock = threading.Lock()


def get_job(job_id: str) -> Job | None:
    with _lock:
        return _jobs.get(job_id)


def current_job() -> Job | None:
    with _lock:
        return _current


def is_rebuilding() -> bool:
    job = current_job()
    return job is not None and job.status == "running"


def _run(job: Job, release: Callable[[], None], reopen: Callable[[], None]) -> None:
    global _current
    from parakh import database, pipeline

    try:
        release()

        job.step, job.step_label = 0, STEPS[0]
        pipeline.run()

        job.step, job.step_label = 1, STEPS[1]
        database.build_database()

        job.step, job.step_label = 2, STEPS[2]
        try:
            from parakh.validation.build import build_validation_tables

            build_validation_tables()
        except Exception:
            # Validation tables are additive and the /validation page
            # degrades without them; a failure here must not strand the
            # corpus itself, which is already rebuilt and correct.
            traceback.print_exc()

        job.status = "done"
    except Exception as exc:  # noqa: BLE001 — reported to the caller verbatim
        traceback.print_exc()
        job.status = "error"
        job.error = f"{type(exc).__name__}: {exc}"
    finally:
        job.finished_at = _now()
        try:
            reopen()
        except Exception:  # noqa: BLE001
            traceback.print_exc()
        with _lock:
            if _current is job:
                _current = None


def start_rebuild(
    reason: str,
    release: Callable[[], None],
    reopen: Callable[[], None],
) -> Job:
    """Kick off a rebuild in a background thread. One at a time."""
    global _current
    with _lock:
        if _current is not None and _current.status == "running":
            raise RuntimeError("A rebuild is already running.")
        job = Job(id=uuid.uuid4().hex[:12], reason=reason)
        _jobs[job.id] = job
        _current = job

    thread = threading.Thread(
        target=_run, args=(job, release, reopen), name=f"parakh-rebuild-{job.id}", daemon=True
    )
    thread.start()
    return job
