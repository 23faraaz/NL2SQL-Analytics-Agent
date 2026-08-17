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
  deterministic SQL against the      understand + generate (1 LLM call) →
  existing views, no LLM             validate (sql_validator) → execute
                                      → explain (LLM, non-metric results
                                      only) → suggest follow-ups
                                      (deterministic)
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
- `app/llm/` — provider-independent NL2SQL orchestration, behind an
  `LLMProvider` abstraction so the active provider is chosen by the
  `LLM_PROVIDER` environment variable, not hardcoded:
  - `base.py` — the `LLMProvider` interface and the shared `LLMError`.
  - `pipeline.py` — `understand_and_generate_sql` (combined understanding
    + SQL generation, one call), `regenerate_sql`, `explain_results`
    (skipped for single-value metric results -- see
    `main.is_single_value_metric_result`), and deterministic
    `suggest_followups` (no LLM call).
  - `factory.py` — resolves `LLM_PROVIDER` to a concrete provider.
  - `gemini_provider.py` / `groq_provider.py` — provider-specific SDK
    calls, config validation, timeouts, and retry/rate-limit handling.
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
