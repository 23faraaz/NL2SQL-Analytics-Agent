# Production architecture decisions

Status: proposed baseline for Phase 3

This document defines the constraints that must be agreed before production
Terraform and deployment automation are treated as operationally ready.

## 1. Service objective and cost posture

The initial production environment is a low-traffic portfolio/small-service
deployment, not a high-availability regulated platform.

- Region: `eu-west-2`.
- Runtime: Amazon ECS on Fargate.
- Deployment target: one ECS service behind an Application Load Balancer.
- Availability: two Availability Zones for load balancer, application tasks,
  and database subnet placement.
- Cost posture: prefer managed AWS capabilities, but do not introduce Amazon
  Managed Service for Prometheus or Amazon Managed Grafana until application
  metrics and PromQL dashboards justify their additional cost and complexity.
- Production must have an explicit monthly budget and billing alarms before it
  is left running continuously.

The owner must still choose the maximum monthly budget, required uptime,
recovery point objective, and recovery time objective before provisioning RDS.

## 2. Pipeline separation

Infrastructure changes and routine application releases use separate workflows.

### Infrastructure workflow

Owns networking, IAM, RDS, ECS foundations, ALB, DNS, certificates, logging,
alarms, and dashboards. It performs Terraform validation, security scanning,
a reviewable plan, production approval, and application of the exact plan.

### Application release workflow

Consumes an image digest already built, tested, scanned, and published by CI.
It may register a new task-definition revision and update the ECS service. It
must not have permission to modify networking, RDS, broad IAM policy, or its own
OIDC trust policy.

The current `.github/workflows/cd.yml` is a draft and must be split to follow
this boundary before production use.

## 3. Artifact promotion contract

- CI builds the image once.
- CI tags it `sha-<40-character Git commit>` and records the registry digest.
- Deployment consumes `repository@sha256:<64 hexadecimal characters>`.
- CD never rebuilds or deploys `latest`.
- Commit, workflow run, repository, digest, and task-definition revision are
  recorded for every deployment.

## 4. Identity and permissions

- GitHub authenticates to AWS with OIDC; no static AWS access keys are stored.
- Trust uses the immutable GitHub owner and repository identifiers.
- The CI publishing role trusts only the exact `main` reference.
- The infrastructure plan role is read-only and trusts only the exact `main`
  reference.
- The production apply role trusts the GitHub `production` environment.
- The application deployment role is separate from the infrastructure role.
- `iam:PassRole` is restricted to the exact ECS task and execution roles.
- Deployment roles cannot edit their own policies or OIDC trust.

## 5. Networking

- The ALB is public; ECS tasks and RDS are private.
- Only the ALB security group can reach the ECS application port.
- Only the ECS task security group can reach PostgreSQL.
- The public endpoint uses HTTPS with ACM; HTTP redirects to HTTPS.
- ALB access logging is enabled with a retention policy.

The NAT design requires an explicit decision. One NAT Gateway is cheaper but
creates an Availability Zone dependency. One per AZ improves resilience but
costs more. VPC endpoints for ECR, S3, CloudWatch Logs, and Secrets Manager must
be compared against NAT traffic and hourly costs before implementation.

## 6. Database and migrations

- RDS PostgreSQL is not publicly accessible.
- Storage and backups are encrypted.
- Credentials are generated and stored in Secrets Manager, never Terraform
  variable files, plans, GitHub variables, or container environment files.
- The ECS task role can read only the application database secret.
- Backup retention, deletion protection, Multi-AZ choice, storage autoscaling,
  maintenance windows, and restore testing are explicit production settings.
- Schema changes are performed by a separate, single-run migration task.
- Migrations must be backward-compatible with the previous application revision
  so application rollback remains possible.

## 7. Health contracts

The service exposes different signals for different purposes.

- Liveness: the process is running; it does not call external dependencies.
- Readiness: the task can safely receive traffic and access mandatory local
  dependencies such as PostgreSQL.
- Smoke test: a bounded request through the ALB proves a meaningful application
  path works without modifying production data.
- External AI-provider availability is monitored separately and must not remove
  every otherwise healthy ECS task from the ALB target group.

## 8. Monitoring baseline

Monitoring exists before the first application deployment.

### Initial stack

- CloudWatch Logs for structured JSON application logs.
- ECS Container Insights with enhanced observability for cluster, service,
  task, and container signals.
- Native CloudWatch metrics for ECS, ALB, and RDS.
- CloudWatch dashboards and alarms managed by Terraform.
- EventBridge notifications for failed ECS deployments and stopped tasks.
- SNS notification routing, with the destination configured outside source
  control.

Minimum alarms:

- ECS running task count below desired count.
- ECS CPU and memory saturation.
- ALB unhealthy host count greater than zero.
- ALB target 5xx rate and elevated response latency.
- RDS CPU, free storage, connections, and failover events.
- Application error rate and readiness failures.
- Deployment failure and rollback events.
- AWS budget threshold alarms.

All logs and metrics carry enough context to correlate environment, service,
task, commit SHA, image digest, request ID, and deployment run.

### Prometheus and Grafana

The application should expose a private Prometheus-compatible `/metrics`
endpoint containing bounded-cardinality application metrics such as request
count, duration, error count, database query duration, LLM request duration,
and provider error count. Customer text, SQL text, user identifiers, request
prompts, and unbounded labels must never appear in metric labels.

Prometheus and Grafana are deferred until these application metrics are needed.
When adopted:

- AWS Distro for OpenTelemetry collects metrics from ECS.
- Amazon Managed Service for Prometheus stores and queries them.
- A managed Grafana workspace reads both CloudWatch and Prometheus.
- Alert ownership and duplicate CloudWatch/Prometheus signals are documented.

Self-hosting Prometheus or Grafana on this ECS service is rejected for the
initial release because it adds persistent storage, backup, patching, scaling,
authentication, and monitoring-of-the-monitoring-system responsibilities.

## 9. Deployment and rollback

- Production approval includes the commit, digest, CI evidence, vulnerability
  result, change summary, current task revision, proposed revision, and rollback
  target.
- ECS deployment circuit breaker and rollback are enabled.
- CD waits for service stability, checks target health, and performs the smoke
  test.
- Failure captures ECS service events, stopped-task reasons, target health, and
  bounded CloudWatch diagnostics before rollback.
- The previous task definition remains deployable.
- Database migrations cannot prevent the previous revision from running.

## 10. Delivery order

1. Confirm cost, availability, RPO, and RTO decisions.
2. Define health, secrets, logging, metrics, and migration contracts.
3. Implement remote state, locking, OIDC roles, and permission boundaries.
4. Implement networking, HTTPS, and observability foundations.
5. Implement and test RDS backup and restore behavior.
6. Implement ECS with digest-only task definitions and circuit-breaker rollback.
7. Apply foundational infrastructure through the infrastructure workflow.
8. Replace the draft CD workflow with a narrow application-release workflow.
9. Test a successful deployment and an intentionally unhealthy deployment.
10. Record recovery evidence before declaring Phase 3 complete.
