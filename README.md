# PARAKH

Anomaly flagging for MPLADS implementation records (SIH26102). A review queue,
not a verdict — 13 detectors across two confidence tiers surface works worth a
second look, each flag carrying its own evidence and a benign explanation
alongside it. Once running, `/methodology` explains every detector and
`/validation` shows how they were tested.

## Prerequisites

- **Python 3.11+** (developed on 3.14)
- **Node.js 20+**

## Quick start

The corpus is committed, so a fresh clone runs without any data build.

```bash
git clone https://github.com/Kartik-Garg-13/mplad_sih.git
cd mplad_sih

# Python side
python -m venv .venv
.venv/Scripts/activate          # .venv/bin/activate on macOS/Linux
pip install -e ".[dev]"

# Frontend
npm install --prefix web
```

Then start both servers — both are required.

```bash
# Terminal 1 — API
python -m uvicorn parakh.api.main:app --port 8020

# Terminal 2 — frontend
npm --prefix web run dev -- --port 3010
```

Open **http://localhost:3010**.

The frontend reads `NEXT_PUBLIC_API_URL` and falls back to
`http://localhost:8020`, so no env file is needed for the default setup. To
point it elsewhere, create `web/.env.local` (git-ignored) with
`NEXT_PUBLIC_API_URL=<url>`.

Add `--reload --reload-dir src` to the uvicorn command when working on the API.

## Rebuilding the data

Only needed after changing a detector, the parsing, or the raw exports —
`data/processed/` is already committed. Every rebuild is deterministic and takes
a few seconds; nothing in this app computes a detector live.

```bash
python -m parakh.pipeline            # raw CSVs -> data/processed/*.parquet
python -m parakh.database            # parquet + detectors -> parakh.duckdb
python -m parakh.validation.build    # validation results -> same duckdb
```

**Stop the API server first.** The rebuild swaps the DuckDB file atomically via
`os.replace()`, which fails on Windows while another process holds it open.

Raw eSAKSHI exports live in `data/raw/esakshi_ls_18ls/` and
`data/raw/esakshi_rs_18ls/` — hand-downloaded from `mplads.mospi.gov.in`, no
scraper. `src/parakh/config.py` lists the exact filenames expected.

## Tests

```bash
pytest                    # 147 tests, ~25s
npm --prefix web run lint # must be clean
npm --prefix web run build
```

Stop the API server before running `pytest` — some tests rebuild the database
and hit the same Windows file lock described above. The frontend build
type-checks as it goes and has caught errors that dev mode hid, so treat it as
part of the test suite rather than a release step.

`tests/test_vocabulary_lock.py` greps `web/src` for words that would turn a
flag into an accusation. If it fails, rewrite the copy — never extend the
allowlist.

## Layout

```
src/parakh/          pipeline, detectors, validation, FastAPI app
  detectors/         tier_a.py (A1-A5), tier_b.py (B1-B8)
  validation/        five independent validation methods
  api/main.py        read-only API over the DuckDB store
web/src/app/         Next.js App Router pages
data/raw/            eSAKSHI exports as downloaded
data/processed/      built parquet + parakh.duckdb + overrides.sqlite
docs/                presenter brief, demo script
tests/               147 tests
```

## Reviewer overrides

`data/processed/overrides.sqlite` is deliberately a separate store from
`parakh.duckdb`, so rebuilding the database never wipes a reviewer's
"reviewed — explained" marks. It is the one file here that holds state the
pipeline cannot regenerate — back it up separately before a fresh data pull.
