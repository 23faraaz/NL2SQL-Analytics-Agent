# Phase 3: Production infrastructure and continuous deployment

Status: in progress

The detailed architectural constraints are defined in
`docs/production-architecture-decisions.md`. This plan is the implementation
sequence and completion checklist.

## Step 1 — Architecture and operational contracts

- [x] Separate infrastructure changes from routine application releases.
- [x] Promote only the immutable image digest produced by CI.
- [x] Define secrets, health, database migration, observability, and rollback
  contracts.
- [ ] Record the approved monthly budget, availability target, RPO, and RTO.

## Step 2 — Production Terraform foundation

- [ ] Configure encrypted S3 remote state with native locking.
- [ ] Pin Terraform and provider versions and commit the dependency lock file.
- [ ] Add production providers, validated variables, locals, and outputs.
- [ ] Make `terraform fmt`, initialization without a backend, and validation
  pass in CI.

## Step 3 — Networking and HTTPS

- [ ] Deploy public ALB subnets and private application/database subnets across
  two Availability Zones.
- [ ] Allow ALB-to-ECS and ECS-to-RDS traffic only on required ports.
- [ ] Use ACM-backed HTTPS and redirect HTTP to HTTPS.
- [ ] Record the accepted NAT resiliency/cost tradeoff.

## Step 4 — Observability foundation

- [ ] Create structured CloudWatch log groups with retention.
- [ ] Enable ECS Container Insights with enhanced observability.
- [ ] Create ECS, ALB, and RDS alarms and a production dashboard.
- [ ] Route deployment failure events through EventBridge and SNS.
- [ ] Configure an AWS budget alarm.
- [ ] Keep Prometheus-compatible application metrics bounded in cardinality;
  add ADOT, Managed Prometheus, and managed Grafana only when required.

## Step 5 — Database and migrations

- [ ] Create private encrypted RDS PostgreSQL with AWS-managed master password.
- [ ] Enable backups, deletion protection, logs, and performance monitoring.
- [ ] Restrict database access to the ECS task security group.
- [x] Run the application-role bootstrap as a single-purpose task before
  service activation; keep destructive local schema loaders out of production.
- [x] Add forward-only, versioned production schema migrations with immutable
  checksums before loading production data.
- [ ] Prove backup restoration and backward-compatible rollback.

## Step 6 — ECS runtime

- [ ] Create a Fargate cluster, task definition, service, and least-privilege
  execution/task roles.
- [ ] Reject mutable or tag-only image references.
- [ ] Inject secret ARNs rather than secret values.
- [ ] Enable deployment circuit-breaker rollback and ALB health checks.

## Step 7 — GitHub OIDC roles

- [ ] Use separate roles for infrastructure planning, infrastructure apply,
  and narrow application deployment.
- [ ] Restrict trust to immutable repository identity, exact main reference,
  and the production environment as appropriate.
- [ ] Restrict `iam:PassRole` and prevent roles from editing their own trust or
  permissions.

## Step 8 — Infrastructure workflow

- [ ] Validate and security-scan Terraform.
- [ ] Generate a readable and binary plan with destructive changes highlighted.
- [ ] Require production approval and apply only the reviewed plan.
- [ ] Reject expired plans and preserve audit metadata.

## Step 9 — Application release workflow

- [ ] Start only from a successful main-branch CI run.
- [ ] Validate CI metadata and deploy the exact ECR digest without rebuilding.
- [ ] Register a task-definition revision and update only the ECS service.
- [ ] Record the prior revision as the rollback target.

## Step 10 — Verification and recovery exercise

- [ ] Wait for ECS stability and healthy ALB targets.
- [ ] Run readiness and bounded smoke tests through the ALB.
- [ ] Capture ECS, target health, and CloudWatch diagnostics on failure.
- [ ] Deliberately deploy an unhealthy revision and prove automatic rollback.
- [ ] Reconcile Terraform state after rollback and document the runbook.

Phase 3 is complete only when every unchecked item has evidence from the live
AWS and GitHub environments. Code existing in the repository is not, by itself,
completion evidence.
