# Commerce Intelligence

A natural-language analytics assistant over a real e-commerce dataset: ask a
question in plain English, get a validated, read-only SQL query, a chart, and
a plain-English explanation. A separate deterministic Customer Analytics
dashboard (top customers, order history, value tiers) answers fixed business
questions directly against the database, without going through the LLM.

See `docs/architecture.md` for the full data flow, `docs/security.md` for the
SQL safety model, and `docs/troubleshooting.md` for common setup problems.

## How it works

```
Raw Olist CSVs → ETL (real data) → synthetic augmentation → commerce schema
                                                                    │
                                              ┌─────────────────────┤
                                              ▼                     ▼
                                     Customer Analytics        NL2SQL chat
                                     (deterministic SQL)     (Gemini → SQL
                                                              validator → DB)
```

## Prerequisites

- Docker and Docker Compose (recommended path), **or** Python 3.12 and a local
  PostgreSQL 16 instance.
- A Gemini API key and a valid Gemini model ID for that key.
- The real Olist Brazilian E-Commerce Public Dataset, placed in `data/raw/`
  (see `data/raw/README.md`) — **not** included in this repository.

## Setup

```bash
cp .env.example .env
# edit .env: set DB_PASSWORD, GEMINI_API_KEY, and GEMINI_MODEL
```

`GEMINI_MODEL` has no default on purpose — the app fails fast at startup with
a clear error if it (or `GEMINI_API_KEY`) is unset, rather than silently
guessing a model name that may not be valid for your access. Check the
current Gemini API model list for a value.

## Run with Docker Compose

```bash
docker compose down -v --remove-orphans
docker compose up --build
```

This builds the app image and a separate one-shot `db-init` image, starts
PostgreSQL, waits for it to be healthy, then `db-init` creates the `commerce`
schema and runs the full pipeline (real ETL → synthetic augmentation → load)
before the app starts. The app will not start until `db-init` completes
successfully. Visit `http://localhost:8501`.

## Run locally without Docker

```bash
pip install -r requirements.txt -r requirements-etl.txt
python -m scripts.run_etl
python -m scripts.run_augmentation
python -m scripts.load_commerce
streamlit run app/main.py
```

## Tests

```bash
pip install -r requirements-dev.txt
pytest                        # full suite; DB-dependent tests skip cleanly
                               # if no PostgreSQL is reachable
pytest -m integration         # only the tests that require a real database
                               # -- confirms they actually ran, not skipped
pytest -m "not integration"   # only dependency-free unit tests
```

## Project layout

- `app/` — the Streamlit application (chat pipeline, SQL validator, Customer
  Analytics service, DB access).
- `etl/` — the real Olist ETL (`etl/transform/`) and synthetic augmentation
  (`etl/augment/`) pipelines.
- `scripts/` — CLI entry points (`run_etl`, `run_augmentation`,
  `load_commerce`) and `scripts/legacy/` (superseded, kept for history, not
  used by anything).
- `sql/` — the canonical `commerce` schema, views, and indexes.
- `docs/` — architecture, security, and troubleshooting notes;
  `docs/data_mapping.md` records exactly which column in the schema is real,
  derived, synthetic, or a default, and why.
- `tests/` — pytest suite (unit tests always run; integration tests need a
  real PostgreSQL, see above).
