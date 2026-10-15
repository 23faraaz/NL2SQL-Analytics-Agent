# NL2SQL Analytics Agent

[![CI](https://github.com/23faraaz/NL2SQL-Analytics-Agent/actions/workflows/ci.yml/badge.svg)](https://github.com/23faraaz/NL2SQL-Analytics-Agent/actions/workflows/ci.yml)
[![Terraform](https://img.shields.io/badge/IaC-Terraform-7B42BC?logo=terraform)](terraform/)
[![AWS](https://img.shields.io/badge/AWS-ECS%20Fargate-FF9900?logo=amazonaws)](docs/production-architecture-decisions.md)
[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12-3776AB?logo=python&logoColor=white)](.github/workflows/ci.yml)

A Terraform-managed personal production system that turns natural-language
questions into validated, read-only PostgreSQL analytics over the Olist
e-commerce dataset. The project demonstrates the complete cloud delivery
lifecycle: infrastructure as code, private networking, immutable containers,
OIDC-based CI/CD, security gates, monitoring, rollback, database restoration,
and idempotent data imports.

The public deployment uses `faraazmo.co.uk` when the cost-controlled AWS
environment is running. This is a personal production environment with
documented availability and cost trade-offs, not a business-critical service
with a contractual SLA.

## What this project demonstrates

- Reusable Terraform modules for a two-AZ VPC, public ALB, private ECS tasks,
  private RDS PostgreSQL, IAM, logging, alarms, and encrypted storage.
- GitHub Actions authentication to AWS through OIDC with separate plan, apply,
  image-publishing, data-import, and application-deployment roles.
- Build-once artifact promotion: CI scans an immutable image and CD deploys the
  exact ECR digest without rebuilding it.
- Protected production approval, ECS stability checks, ALB target validation,
  public HTTPS smoke testing, and automatic rollback on failed deployment.
- Versioned and KMS-encrypted dataset releases imported by a one-off Fargate
  task with an immutable ledger and repeat-run idempotency checks.
- Tested RDS point-in-time restoration, CloudWatch alarms, EventBridge
  deployment-failure notifications, SNS email delivery, and AWS Budgets.
- Reproducible local development through Docker Compose, including an automated
  regression proving database initialization succeeds on repeated starts.

## Architecture

[![NL2SQL Analytics Agent personal-production AWS architecture](docs/architecture/aws-production-architecture.drawio.png)](docs/architecture/aws-production-architecture.drawio.png)

The PNG retains its embedded draw.io model, so the same tracked file is both the
rendered diagram and the editable architecture source.

```text
User ── DNS lookup ──> Cloudflare DNS (DNS only)
User ── HTTPS 443 ──> ALB + ACM ── HTTP 8501 ──> ECS Fargate tasks
                                                      │
                                                      ├──> RDS PostgreSQL
                                                      └──> NAT ──> Gemini/Groq

GitHub Actions ── OIDC ──> IAM ──> ECR / Terraform / ECS
S3 dataset release ──> one-off importer task ──> RDS PostgreSQL
ALB / ECS / RDS ──> CloudWatch / EventBridge ──> SNS ──> operator
```

The VPC spans `eu-west-2a` and `eu-west-2b`. The internet-facing ALB is
attached to both public subnets. Two Streamlit tasks run with no public IPs in
private subnets, and their security group accepts port 8501 only from the ALB.
RDS is private and accepts PostgreSQL traffic only from the ECS task security
group. A single NAT Gateway provides outbound access for AWS APIs and the
external LLM provider.

### Core AWS services

| Area | Services | Purpose |
|---|---|---|
| Network | VPC, two AZs, public/private subnets, IGW, NAT, security groups | Isolate workloads and restrict service-to-service traffic |
| Edge | Cloudflare DNS, ALB, ACM | Custom-domain DNS, HTTPS termination, health checks, and multi-AZ ingress |
| Compute | ECS Fargate, Application Auto Scaling | Run two persistent Streamlit tasks plus one-off importer and migration tasks |
| Data | RDS PostgreSQL, S3, KMS, Secrets Manager | Store analytics data and protect datasets, credentials, logs, and state |
| Delivery | ECR, GitHub Actions, IAM OIDC | Build, scan, publish, approve, and deploy immutable container digests |
| Operations | CloudWatch, EventBridge, SNS, AWS Budgets | Observe health, notify the operator, and warn about cost |

## Delivery pipeline

```text
Pull request
  └─> Ruff + Black + Python 3.11/3.12 tests
      └─> repeated-Compose regression + Terraform validation + Trivy
          └─> main only: publish scanned image digest to ECR
              └─> protected production approval
                  └─> ECS deployment
                      ├─> stable + healthy + HTTPS smoke test: release
                      └─> unhealthy: automatic rollback
```

Pull requests cannot request AWS credentials. A successful `main` build is the
only path that publishes images, and CD accepts release metadata only from that
successful CI run. See [CI artifact promotion](docs/ci-cd.md) and the
[production architecture decisions](docs/production-architecture-decisions.md).

## Security and reliability controls

- No long-lived AWS access keys in GitHub; workflows use short-lived OIDC
  sessions and narrowly scoped IAM roles.
- ECS tasks and RDS have no public IPs. Security-group references enforce
  `Internet → ALB → ECS → RDS` rather than broad database ingress.
- Secrets are injected from Secrets Manager and are not stored in Git,
  Terraform variable files, or container images.
- Generated SQL passes an AST-based read-only validator and executes with a
  database statement timeout before results reach the UI.
- Runtime dependencies are fully pinned with hashes. Trivy blocks fixable HIGH
  and CRITICAL findings in both application and importer images.
- RDS encryption, deletion protection, automated backups, restore testing, and
  forward-only migrations protect the data path.
- Dataset imports verify the exact S3 object version and bundle SHA-256, then
  use an import ledger to make retries safe.

Read the detailed [SQL safety model](docs/security.md), [production runbook](docs/production-runbook.md),
and [operations checklist](docs/PRODUCTION_OPERATIONS_CHECKLIST.md).

## Verified operational evidence

This repository distinguishes configuration from proof. The full evidence log
is maintained in [EXECUTION_PLAN.md](docs/EXECUTION_PLAN.md). Verified exercises
include:

- Successful public HTTPS deployment at `faraazmo.co.uk` through an immutable
  ECR digest.
- A deliberately unhealthy ECS revision that failed after repeated starts and
  rolled back while the public endpoint remained healthy.
- RDS point-in-time restoration with independent row-count validation, followed
  by deletion of the temporary restored instance.
- Initial and repeated production imports with identical expected row counts.
- A controlled CloudWatch alarm test that reached the confirmed SNS email
  subscription and was restored to `OK`.
- Local and CI repeated-Compose tests proving database initialization is a safe
  no-op when persisted tables match the processed dataset.

Recent consolidated proof: [CI run 38682770353](https://github.com/23faraaz/NL2SQL-Analytics-Agent/actions/runs/38682770353)
published the scanned images, and [CD run 38683221055](https://github.com/23faraaz/NL2SQL-Analytics-Agent/actions/runs/38683221055)
deployed them successfully through ECS stability, target-health, and HTTPS
smoke-test gates.

## Deliberate trade-offs

This architecture is production-shaped for learning and demonstration, not the
cheapest way to host a low-traffic Streamlit application.

| Decision | Accepted consequence |
|---|---|
| Single-AZ RDS | Database maintenance or an AZ failure can interrupt the whole service |
| One NAT Gateway | Lower complexity, but one AZ-level outbound dependency and possible cross-AZ charges |
| One-day automated backup retention | Matches the approved 24-hour RPO but provides limited recovery history |
| Personal email alert ownership | Appropriate for one operator; not equivalent to a staffed on-call rotation |
| Best-effort 99% objective | No contractual SLA; recovery is operator-attended with a four-hour RTO target |
| USD 20 budget warning | An alert, not a cap; the full stack is estimated at roughly USD 130–160/month before VAT |

The environment should remain running only for demonstrations or evidence
collection. The [cost and teardown handoff](docs/PORTFOLIO_COST_HANDOFF.md)
documents snapshot preservation, destroy review, teardown, and reconstruction.

## Application and data flow

```text
Raw Olist CSVs ──> deterministic ETL ──> seeded synthetic augmentation
       └───────────────────────────────> PostgreSQL commerce schema
                                              ├─> deterministic customer analytics
                                              └─> NL2SQL → validate → execute → chart
```

Every populated field is classified as real, derived, synthetic, or default in
the [data mapping](docs/data_mapping.md). Fixed customer analytics use known
SQL directly; only free-form questions use Gemini or Groq to generate SQL.

## Run locally

### Prerequisites

- Docker Engine and Docker Compose.
- The Olist Brazilian E-Commerce Public Dataset in `data/raw/`; it is not
  included in this repository. See [the dataset instructions](data/raw/README.md).
- A supported Gemini or Groq API key and model identifier.

```bash
cp .env.example .env
# Set DB_PASSWORD and the selected LLM provider credentials in .env.
docker compose up --build
```

Compose starts PostgreSQL, waits for it to become healthy, transforms and loads
the dataset through a one-shot `db-init` container, then starts Streamlit at
`http://localhost:8501`. On repeated starts, initialization succeeds without
duplicating data when database and processed-file counts match; inconsistent
partial state is rejected rather than overwritten.

### Run without Docker

```bash
python -m pip install --require-hashes -r requirements.txt
python -m pip install --require-hashes -r requirements-etl.txt
python -m scripts.run_etl
python -m scripts.run_augmentation
python -m scripts.load_commerce
streamlit run app/main.py
```

## Test and validate

```bash
python -m pip install --require-hashes -r requirements-dev.txt
ruff check .
black --check .
pytest -m "not integration" --strict-markers

# Isolated PostgreSQL volume; runs database initialization twice.
DB_NAME=nl2sql_compose_regression \
DB_USER=nl2sql_test \
DB_PASSWORD=compose-regression-only \
bash tests/integration/compose-repeated-up.sh
```

Database-dependent pytest cases use the `integration` marker and skip cleanly
when PostgreSQL is unavailable.

## Repository map

| Path | Responsibility |
|---|---|
| `app/` | Streamlit UI, NL2SQL orchestration, SQL validation, charts, and deterministic customer analytics |
| `etl/` | Olist transformations, validation, and deterministic synthetic augmentation |
| `scripts/` | ETL, augmentation, schema loading, S3 import, and database bootstrap entry points |
| `sql/` | Canonical commerce schema, views, indexes, and forward-only migrations |
| `terraform/` | Bootstrap, global, staging, production, and reusable AWS modules |
| `.github/workflows/` | CI, immutable application CD, infrastructure plan/apply, and dataset import |
| `tests/` | Unit, database integration, regression, and Compose lifecycle coverage |
| `docs/` | Architecture decisions, security model, runbooks, cost posture, and evidence |

## Documentation

- [Production architecture decisions](docs/production-architecture-decisions.md)
- [CI/CD trust and artifact promotion](docs/ci-cd.md)
- [Production deployment runbook](docs/production-runbook.md)
- [Production operations checklist](docs/PRODUCTION_OPERATIONS_CHECKLIST.md)
- [Execution evidence](docs/EXECUTION_PLAN.md)
- [Cost and teardown handoff](docs/PORTFOLIO_COST_HANDOFF.md)
- [SQL security model](docs/security.md)
- [Data provenance mapping](docs/data_mapping.md)
- [Troubleshooting](docs/troubleshooting.md)
