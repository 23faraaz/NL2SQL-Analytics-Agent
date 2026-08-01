# Architecture

## Data flow

```
Raw Olist CSVs (data/raw/, operator-supplied)
      │
      ▼
etl/transform/*.py   -- S4a: real + derived fields only
      │
      ▼
etl/augment/*.py     -- S4b: synthetic fields Olist cannot provide
      │                (customer identity, product identity, variants),
      │                seeded and deterministic
      ▼
scripts/load_commerce.py
      │                creates the commerce schema (sql/001-003.sql) and
      │                loads all 8 tables, FK-safe order
      ▼
commerce.* (PostgreSQL): 15 tables, 7 analytics views
      │
      ├──────────────────────────┐
      ▼                          ▼
app/services/customer_service.py   app/main.py chat pipeline
  deterministic SQL against the      understand → generate (Gemini) →
  existing views, no LLM             validate (sql_validator) → execute
                                      → explain → suggest follow-ups
```

Every populated column is classified REAL / DERIVED / SYNTHETIC / DEFAULT in
`docs/data_mapping.md` — that document is the source of truth for what in the
database is genuine Olist data versus generated to complete the schema.

## Why two data paths into the same schema

Customer Analytics answers a small, fixed set of business questions
(top-N customers, order history, value tiers). Routing fixed questions
through an LLM would add latency, cost, and a source of non-determinism for
answers that don't need it — the SQL for these is known in advance and
reused directly from `commerce.customer_lifetime_metrics` /
`commerce.order_financials`. Free-form questions still go through the full
NL2SQL pipeline, because their SQL genuinely isn't known in advance.

## Module responsibilities

- `app/db.py` — connection handling, schema introspection (feeds the LLM
  prompt), read-only query execution with a statement timeout.
- `app/llm.py` — the four Gemini calls (understand, generate, explain,
  suggest follow-ups) and startup config validation.
- `app/sql_validator.py` — the safety gate between LLM-generated SQL and the
  database (see `docs/security.md`).
- `app/services/` — `analytics_service.py` (executes validated SQL for the
  chat path), `customer_service.py` (deterministic Customer Analytics
  queries), `chart_service.py` (rule-based chart selection).
- `etl/` and `scripts/` — see `README.md`'s project layout.

## Known architectural limitations

- The `commerce` schema also defines `refunds`, `campaigns`,
  `discount_codes`, `customer_segments`, and `inventory_movements` — created,
  but not populated in this milestone. Views that join against them degrade
  gracefully (`LEFT JOIN` + `COALESCE`) rather than breaking.
- The synthetic augmentation seed volume (a handful of fixture-scale
  customers/orders in this sandbox) means value-tier thresholds
  (`sql/002_views.sql`) don't discriminate meaningfully yet — expected to
  resolve once the real Olist-scale dataset is loaded.
