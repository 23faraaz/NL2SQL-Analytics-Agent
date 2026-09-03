# Production deployment runbook

This runbook completes the live AWS and GitHub checkpoints for Phase 3. Do not
claim Phase 3 complete until the evidence section is filled in.

## 1. Required decisions

Record before provisioning:

- Monthly AWS budget: proposed default USD 75.
- Availability: proposed cost-optimized two-AZ application with a single NAT
  Gateway and single-AZ RDS.
- RPO: proposed 24 hours or better with seven-day automated backups.
- RTO: proposed four hours for this portfolio environment.

If this is a business-critical service, reject those defaults: use Multi-AZ RDS,
one NAT Gateway per AZ or validated VPC endpoints, a tested restore procedure,
and objectives approved by the service owner.

## 2. Bootstrap prerequisites

1. Apply `terraform/bootstrap` from a trusted administrator workstation to
   create the versioned, customer-KMS-encrypted, private state bucket. Record
   both `state_bucket_name` and `state_kms_key_arn` outputs.
2. Apply `terraform/global` to create ECR, the GitHub OIDC provider, CI publish
   role, read-only plan role, and production apply role.
3. Review the production apply policy and permission boundary. Do not grant the
   apply role permission to modify itself or the plan role.
4. Create or import an ACM certificate in `eu-west-2` for the production DNS
   name.
5. Create two Secrets Manager secrets without passing their values through
   Terraform:
   - application provider configuration with `GROQ_API_KEY` and `GROQ_MODEL`;
   - least-privilege database application password with a `password` JSON key.
6. Create the `nl2sql_app` PostgreSQL role through a controlled migration task;
   do not use the RDS master secret in the long-running application service.

## 3. GitHub configuration

Create a GitHub environment named `production` with:

- required reviewer;
- prevention of self-review when supported;
- deployment branches restricted to `main`;
- no static AWS access keys.

Repository/environment variables required by the workflows:

```text
AWS_ACCOUNT_ID
AWS_REGION
AWS_ECR_REPOSITORY_NAME
AWS_CI_PUBLISH_ROLE_ARN
AWS_TERRAFORM_PLAN_ROLE_ARN
AWS_TERRAFORM_APPLY_ROLE_ARN
AWS_APPLICATION_DEPLOY_ROLE_ARN
TF_STATE_BUCKET
TF_STATE_KMS_KEY_ARN
TF_PRODUCTION_PUBLIC_SUBNETS
TF_PRODUCTION_PRIVATE_SUBNETS
TF_PRODUCTION_NAT_GATEWAY_SUBNET_KEY
PRODUCTION_CERTIFICATE_ARN
APPLICATION_SECRET_ARN
DATABASE_APPLICATION_SECRET_ARN
PRODUCTION_OIDC_SUBJECT
ECS_CLUSTER_NAME
ECS_SERVICE_NAME
ALB_TARGET_GROUP_ARN
PRODUCTION_HEALTH_URL
APPLICATION_LOG_GROUP_NAME
```

The subnet variables are JSON maps matching
`terraform/environments/production/terraform.tfvars.example`. ARNs and resource
names are identifiers, but access to changing production variables must still
be restricted.

## 4. Infrastructure deployment

1. Obtain an immutable `repository@sha256:...` image from a successful CI run.
2. Run `Production infrastructure` manually from `main` with that image URI
   and `activate_service=false`. This creates the service at zero tasks.
3. Review create/update/delete/replacement counts and download
   `production-plan.txt`.
4. Reject unexplained IAM, security-group, database replacement, public access,
   or deletion changes.
5. Approve the `production` environment only after review. The workflow applies
   the exact plan and runs the idempotent database bootstrap task. Do not
   activate the service if that task fails.
6. Run `Production infrastructure` again with the same immutable image and
   `activate_service=true`. Review and approve this second plan. The bootstrap
   runs again safely before the service scales to two tasks.
7. Save both workflow URLs and Terraform outputs as evidence.
8. Configure the application deployment role and runtime identifiers from the
   outputs as GitHub environment variables.

The bootstrap task creates or reconciles only the `nl2sql_app` login and its
read-only grants. It does not execute `sql/001_schema.sql`, because that local
development loader drops existing tables. Production schema changes require
separate, forward-only versioned migrations.

## 5. Application release

Merging to `main` runs CI. A successful CI run publishes one immutable image and
triggers `CD`. CD validates the artifact, pauses for production approval,
registers a new task-definition revision, updates only the ECS service, waits
for stability, checks target health, and requires the Streamlit health response
to equal `ok`.

CD must never build an image or use the Terraform infrastructure apply role.

## 6. Failure diagnostics

On failure, preserve:

- GitHub workflow and CI run IDs;
- commit SHA and image digest;
- previous and failed task-definition ARNs;
- the latest ECS service events;
- stopped-task reasons;
- target health descriptions;
- the bounded CloudWatch log output captured by CD;
- alarm and dashboard state around the deployment window.

The workflow returns the service to the prior task definition and waits for
stability. The workflow remains failed so the release is not mistaken for a
success.

## 7. Required rollback exercise

1. Build a deliberately unhealthy test image through the same CI process on a
   controlled commit.
2. Confirm Trivy and all non-health tests still pass so deployment reaches ECS.
3. Approve the controlled production exercise.
4. Verify ECS circuit breaker or CD detects the unhealthy revision.
5. Verify the previous task definition is restored and becomes stable.
6. Verify production health returns `ok` after rollback.
7. Confirm alerts fire and diagnostics identify the failure.
8. Check the ECS service against Terraform state. The service task-definition
   field is deliberately ignored by Terraform because application releases own
   it; document the deployed revision separately.

## 8. Monitoring verification

Before completion, verify:

- structured application logs arrive with the expected retention;
- Container Insights shows task/container metrics;
- dashboard widgets display ECS, ALB, and RDS signals;
- an alarm test reaches the confirmed notification destination;
- ECS deployment failure events reach SNS;
- ALB access logs arrive in the encrypted private bucket;
- the AWS budget exists and its notification is confirmed;
- no prompt, customer data, SQL text, API key, or database password appears in
  logs, metric dimensions, alarm text, or workflow artifacts.

## 9. Completion evidence

Do not use **Re-run all jobs** on an already published CI commit to trigger a
release. Container rebuilds are not guaranteed to be byte-for-byte identical,
and the immutable ECR tag guard correctly rejects a different image for the
same commit tag. Trigger release verification with a new reviewed commit on
`main`; CD will then consume that successful CI run's recorded registry digest.

Record:

```text
CI run:
Infrastructure plan run:
Infrastructure apply run:
Successful CD run:
Failed deployment/rollback run:
Restored database test date:
Alarm delivery test date:
Deployed image digest:
Current task-definition ARN:
Reviewer:
```
