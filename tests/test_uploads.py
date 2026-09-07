"""Upload batches join the corpus the same way a built-in house/term does.

Every case here stages a real slice of the shipped Lok Sabha exports rather
than a hand-written fixture: the loaders are strict about composite fields
and date formats, so a synthetic CSV would prove the registry works while
saying nothing about whether a real eSAKSHI export survives the round trip.

The one exception is the work ID itself. A real slice of the shipped file is,
by definition, already in the corpus the shipped file built — so every
fixture here shifts the MP code embedded in the composite work-ID field to a
value far outside the real corpus's range (confirmed below), an injective
transform that keeps every other field (dates, amounts, category text)
untouched and genuinely real, while guaranteeing the row's *identity* is new.
`test_overlap_with_existing_corpus_is_rejected` is the one test that
deliberately skips this shift, to prove the overlap guard itself works.
"""

from __future__ import annotations

import re

import pytest

from parakh import config, uploads
from parakh.ingest import load_stage_both_houses, stage_path

_SRC = config.RAW_DIR / "esakshi_ls_18ls"
_NAMES = config.FILES["lok_sabha_18"]

# The real corpus's MP codes top out at 18475 (confirmed against the built
# corpus) — offsetting by 900000 lands every shifted ID far outside any
# plausible real range while staying injective (distinct originals stay
# distinct), so a 199-row slice can't collide with itself either.
_ID_SHIFT = 900_000
_MP_CODE_RE = re.compile(r"(WS/\s*MP)(\d+)")


def _shift_ids(text: str) -> str:
    return _MP_CODE_RE.sub(lambda m: f"{m.group(1)}{int(m.group(2)) + _ID_SHIFT}", text)


def _slice(stage: str, n: int = 200, shift_ids: bool = True) -> bytes:
    lines = (_SRC / _NAMES[stage]).read_text(encoding="utf-8").splitlines(keepends=True)
    text = "".join(lines[:n])
    if shift_ids:
        text = _shift_ids(text)
    return text.encode("utf-8")


@pytest.fixture
def staged():
    """Register a batch and guarantee it is removed even if the test fails.

    A leaked batch would sit in data/raw/ and silently inflate every later
    pipeline run, so cleanup is a finally, not a trailing statement.
    """
    created: list[str] = []

    def _make(label="Test Batch", stages=("recommended", "sanctioned"), **kw):
        batch = uploads.create_batch(
            label=label,
            house=kw.pop("house", "Test House"),
            term=kw.pop("term", "18th"),
            files={s: (_NAMES[s], _slice(s)) for s in stages},
            **kw,
        )
        created.append(batch["key"])
        return batch

    try:
        yield _make
    finally:
        for key in created:
            uploads.delete_batch(key)


def test_batch_registers_and_is_visible_to_ingest(staged):
    batch = staged()
    assert batch["key"] in config.house_terms()
    assert batch["row_counts"]["recommended"] == 199
    assert stage_path(batch["key"], "recommended") is not None


def test_batch_rows_join_the_corpus_tagged_with_their_source(staged):
    before = load_stage_both_houses("recommended", houses=tuple(config.HOUSE_TERMS)).height
    batch = staged()
    after = load_stage_both_houses("recommended")
    assert after.height == before + 199
    assert (after["house_key"] == batch["key"]).sum() == 199


def test_absent_stage_is_skipped_not_fatal(staged):
    """A partial batch must not break the stages it doesn't provide."""
    batch = staged(stages=("recommended",))
    assert stage_path(batch["key"], "expenditure") is None
    # Expenditure still loads — from the built-in houses alone.
    assert load_stage_both_houses("expenditure").height > 0


def test_recommended_is_required():
    with pytest.raises(uploads.UploadError, match="required"):
        uploads.create_batch(
            label="No Spine",
            house="X",
            term="18th",
            files={"sanctioned": (_NAMES["sanctioned"], _slice("sanctioned"))},
        )


def test_a_file_that_is_not_an_esakshi_export_is_rejected_and_rolled_back():
    with pytest.raises(uploads.UploadError):
        uploads.create_batch(
            label="Junk",
            house="X",
            term="18th",
            files={"recommended": ("junk.csv", b"a,b,c\n1,2,3\n")},
        )
    # Rolled back on both sides: nothing registered, nothing left on disk.
    assert all(b["label"] != "Junk" for b in uploads.list_batches())
    assert not uploads.batch_dir("upload_junk").exists()


def test_overlap_with_existing_corpus_is_rejected():
    """A batch carrying real, already-ingested work IDs must be refused —
    silently accepting it would double-count those works in every detector
    and peer-group statistic (confirmed live: a 59-row overlapping upload
    alone produced 502 spurious A1 flags and 59 spurious A3 flags, neither
    of which fires at all on the clean corpus)."""
    with pytest.raises(uploads.UploadError, match="already exist in the corpus"):
        uploads.create_batch(
            label="Overlapping Batch",
            house="X",
            term="18th",
            files={"recommended": (_NAMES["recommended"], _slice("recommended", shift_ids=False))},
        )
    # Rolled back like any other rejected upload.
    assert all(b["label"] != "Overlapping Batch" for b in uploads.list_batches())
    assert not uploads.batch_dir("upload_overlapping_batch").exists()


def test_builtin_sources_cannot_be_deleted():
    with pytest.raises(uploads.UploadError, match="built-in"):
        uploads.delete_batch("lok_sabha_18")
    assert "lok_sabha_18" in config.house_terms()


def test_keys_do_not_collide(staged):
    first = staged(label="Same Name")
    second = staged(label="Same Name")
    assert first["key"] != second["key"]
