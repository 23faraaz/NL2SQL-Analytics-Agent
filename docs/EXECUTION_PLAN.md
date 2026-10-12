# Phase 3: Production infrastructure and continuous deployment

Status: operational; operator notification destination pending

The detailed architectural constraints are defined in
`docs/production-architecture-decisions.md`. This plan is the implementation
sequence and completion checklist.

## Step 1 — Architecture and operational contracts

- [x] Separate infrastructure changes from routine application releases.
- [x] Promote only the immutable image digest produced by CI.
- [x] Define secrets, health, database migration, observability, and rollback
  contracts.
- [x] Record the approved monthly budget, availability target, RPO, and RTO.

## Step 2 — Production Terraform foundation

- [x] Configure encrypted S3 remote state with native locking.
- [x] Pin Terraform and provider versions and commit the dependency lock file.
- [x] Add production providers, validated variables, locals, and outputs.
- [x] Make `terraform fmt`, initialization without a backend, and validation
  pass in CI.

## Step 3 — Networking and HTTPS

- [x] Deploy public ALB subnets and private application/database subnets across
  two Availability Zones.
- [x] Allow ALB-to-ECS and ECS-to-RDS traffic only on required ports.
- [x] Use ACM-backed HTTPS and redirect HTTP to HTTPS.
- [x] Record the accepted NAT resiliency/cost tradeoff.

## Step 4 — Observability foundation

- [x] Create structured CloudWatch log groups with retention.
- [x] Enable ECS Container Insights with enhanced observability.
- [x] Create ECS, ALB, and RDS alarms and a production dashboard.
- [x] Route deployment failure events through EventBridge and SNS.
- [ ] Add and confirm an operator email for SNS and the USD 20 budget warning.
- [x] Keep Prometheus-compatible application metrics bounded in cardinality;
  defer ADOT, Managed Prometheus, and managed Grafana until required.

## Step 5 — Database and migrations

- [x] Create private encrypted RDS PostgreSQL with AWS-managed master password.
- [x] Enable backups, deletion protection, logs, and performance monitoring.
- [x] Restrict database access to the ECS task security group.
- [x] Run the application-role bootstrap as a single-purpose task before
  service activation; keep destructive local schema loaders out of production.
- [x] Add forward-only, versioned production schema migrations with immutable
  checksums before loading production data.
- [x] Prove point-in-time restoration and backward-compatible application
  rollback.

## Step 6 — ECS runtime

- [x] Create a Fargate cluster, task definition, service, and least-privilege
  execution/task roles.
- [x] Reject mutable or tag-only image references.
- [x] Inject secret ARNs rather than secret values.
- [x] Enable deployment circuit-breaker rollback and ALB health checks.

## Step 7 — GitHub OIDC roles

- [x] Use separate roles for infrastructure planning, infrastructure apply,
  and narrow application deployment.
- [x] Restrict trust to immutable repository identity, exact main reference,
  and the production environment as appropriate.
- [x] Restrict `iam:PassRole` and prevent roles from editing their own trust or
  permissions.

## Step 8 — Infrastructure workflow

- [x] Validate and security-scan Terraform.
- [x] Generate a readable and binary plan with destructive changes highlighted.
- [x] Require production approval and apply only the reviewed plan.
- [x] Reject expired plans and preserve audit metadata.

## Step 9 — Application release workflow

- [x] Start only from a successful main-branch CI run.
- [x] Validate CI metadata and deploy the exact ECR digest without rebuilding.
- [x] Register a task-definition revision and update only the ECS service.
- [x] Record the prior revision as the rollback target.

## Step 10 — Verification and recovery exercise

- [x] Wait for ECS stability and healthy ALB targets.
- [x] Run readiness and bounded smoke tests through the ALB.
- [x] Capture ECS, target health, and CloudWatch diagnostics on failure.
- [x] Deliberately deploy an unhealthy revision and prove automatic rollback.
- [x] Reconcile Terraform state after rollback and document the runbook.

## Live evidence — 2026-10-12

- Public endpoint: `https://faraazmo.co.uk`; health response `ok` over ACM TLS.
- Final CI: run `38268477567`, commit
  `6efde1c671f37068e8cc00eaac1545291012dab0`.
- Final infrastructure plan/apply: run `38271532408`; reviewed task-definition
  and narrow IAM changes only.
- Final CD: run `38269139566`; immutable metadata, ECR digest, ECS stability,
  target health, and public smoke test passed.
- Deployed image: `sha256:3fecda0fc921bac831d8e275f8100117f71bb036e85796ebed860fb898e9c789`.
- Current service: `production-nl2sql:14`, desired/running `2/2`.
- Rollback exercise: deliberately unhealthy revision `production-nl2sql:11`
  failed after four starts; ECS recorded `tasks failed to start` and rolled back
  automatically to revision `:9` while the public endpoint remained healthy.
- Terraform reconciliation: production plan returned `No changes` after the
  rollback exercise.
- Recovery exercise: PITR to `2026-10-12T13:11:20Z`; validation task
  `c99b0571f91d472a89b9ef8281834450` proved 99,441 orders, 99,441 customers,
  102,425 order items, 32,951 products, and 103,886 payments. The temporary
  restore instance was deleted after validation.
- Data incident repair: PRs `#18` and `#19` moved production imports to
  forward-only migrations, checked the immutable ledger before schema work,
  stripped migration BOMs, and added regression coverage. Full suite:
  159 passed, 18 skipped.
- Repaired import: run `38272011763`; exact S3 version and bundle SHA-256
  verified. Independent task `a1e9a12399a84b26959b6eea0216c058` confirmed
  all expected production row counts.
- Idempotency proof: repeat run `38272715175` succeeded; independent task
  `893f2c454549436db0d5ed91f77c519e` confirmed unchanged counts.
- Monitoring: nine alarms are enabled and `OK`; alarm history proves successful
  SNS action publication; the dashboard and EventBridge failure target exist.
  Operator delivery is not complete because SNS has no confirmed subscription
  and the budget has no notification until an email is supplied.

Phase 3 is complete except for confirming the operator notification destination.
Code existing in the repository is not treated as completion evidence; the run
IDs and live AWS observations above are the evidence.
