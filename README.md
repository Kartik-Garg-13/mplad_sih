# PARAKH

Anomaly flagging for MPLADS implementation records (SIH26102). A review queue,
not a verdict — see [`/methodology`](http://localhost:3010/methodology) once
running.

## One-time setup

```bash
# Python side (from the repo root)
python -m venv .venv
.venv/Scripts/activate        # .venv/bin/activate on macOS/Linux
pip install -e ".[dev]"

# Frontend
cd web
npm install
cd ..
```

Raw eSAKSHI exports go in `data/raw/esakshi_ls_18ls/` and
`data/raw/esakshi_rs_18ls/` (see `src/parakh/config.py` for the exact
filenames expected — no scraper, hand-downloaded from
`mplads.mospi.gov.in`).

## Building the data

Every rebuild is deterministic and fast (a few seconds) — nothing in this
app computes a detector live.

```bash
python -m parakh.pipeline            # raw CSVs -> data/processed/*.parquet
python -m parakh.database            # parquet + detectors -> parakh.duckdb
python -m parakh.validation.build    # validation results -> same duckdb (optional, re-run anytime)
```

## Running it

Two servers, both required:

```bash
# Terminal 1 — API (from repo root)
uvicorn parakh.api.main:app --reload --reload-dir src --port 8020

# Terminal 2 — frontend
cd web
npm run dev
```

Open **http://localhost:3010**. The frontend expects the API at
`http://localhost:8020` (set in `web/.env.local` as `NEXT_PUBLIC_API_URL`).

### Production-mode frontend

```bash
cd web
npm run build   # type-checks + lints as part of the build; must be clean
npm run start
```

## Tests

```bash
pytest                 # 123 tests, ~8s
cd web && npm run lint # must be clean
```

## Reviewer overrides

`data/processed/overrides.sqlite` is a separate store from `parakh.duckdb` —
rebuilding the database never wipes a reviewer's "reviewed — explained"
marks. Back it up separately if you want to preserve review state across a
fresh data pull.
