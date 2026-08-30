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

## AWS staging network

The deployed staging VPC spans `eu-west-2a` and `eu-west-2b`. Each Availability
Zone has one public subnet and one private subnet. Automatic public IP
assignment is disabled on every subnet.

The public subnets route outbound traffic through an Internet Gateway. They
will host the internet-facing Application Load Balancer in a later checkpoint.
The private subnets share one route table that sends outbound traffic through a
NAT Gateway in the `public_b` subnet in `eu-west-2b`. The planned ECS tasks will
use the private subnets with public IP assignment disabled.

One NAT Gateway keeps staging simpler than a NAT Gateway in each Availability
Zone. It also reduces the fixed hourly cost. This creates a single-AZ outbound
dependency. Traffic from `eu-west-2a` to the NAT Gateway may also incur
cross-AZ charges. A production environment would normally use one NAT Gateway
per Availability Zone with an AZ-local private route table.

The NAT Gateway provides outbound connectivity. It does not filter outbound
destinations. The application needs this connectivity for ECR, AWS APIs and
the external Gemini or Groq API.

The staging ALB uses HTTP on port 80. Its security group accepts public HTTP
traffic. The ECS task security group accepts application traffic on port 8501
only from the ALB security group. HTTPS is a planned production improvement.
It requires an ACM certificate and an HTTPS listener. The HTTP listener would
then redirect requests to HTTPS.

## Known architectural limitations

- The `commerce` schema also defines `refunds`, `campaigns`,
  `discount_codes`, `customer_segments`, and `inventory_movements` — created,
  but not populated in this milestone. Views that join against them degrade
  gracefully (`LEFT JOIN` + `COALESCE`) rather than breaking.
- The synthetic augmentation seed volume (a handful of fixture-scale
  customers/orders in this sandbox) means value-tier thresholds
  (`sql/002_views.sql`) don't discriminate meaningfully yet — expected to
  resolve once the real Olist-scale dataset is loaded.
