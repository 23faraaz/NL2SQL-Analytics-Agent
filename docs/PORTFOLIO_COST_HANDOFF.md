# Portfolio cost and teardown handoff

## Current posture

The full production-shaped environment is expected to cost roughly USD
130–160 per month before VAT at low traffic. The USD 20 AWS Budget is a warning
threshold, not a spending cap. NAT Gateway, two continuously running Fargate
tasks, the ALB, and RDS are the dominant fixed costs.

The environment should remain intact only while live demonstrations or final
evidence collection are required. Its production verification evidence is now
preserved in Git, GitHub Actions, CloudWatch, and `docs/EXECUTION_PLAN.md`.

## Lower-cost operating profile

Use this only as an explicitly documented portfolio/demo mode:

1. Reduce ECS desired/minimum count from two to one. This saves one task but
   gives up the two-task availability objective.
2. Schedule the ECS service to zero outside demonstration windows. ALB, NAT,
   RDS, KMS, and storage charges continue while tasks are stopped.
3. Stop RDS between short demonstrations, remembering AWS automatically starts
   a stopped RDS instance after seven days.
4. Do not remove the NAT Gateway ad hoc. A no-NAT design requires reviewed VPC
   endpoints or public task networking and corresponding security changes.
5. Re-estimate actual Cost Explorer spend after one complete billing day; do
   not interpret the USD 20 warning as proof the stack fits that budget.

This profile will reduce cost, but it will not reliably reach USD 20 per month.

## Recommended portfolio shutdown

The cheapest safe posture is a reproducible teardown after demonstrations:

1. Confirm `main` is clean and pushed, CI/CD evidence links are recorded, and
   Terraform reports no unexpected managed drift.
2. Create and validate a manual encrypted final RDS snapshot. Record its ARN,
   creation time, engine version, and KMS key.
3. Preserve the immutable dataset S3 version, ECR digests, GitHub variables,
   remote Terraform state, and recovery/import row-count evidence.
4. Produce and review `terraform plan -destroy`. Explicitly check the RDS,
   NAT Gateway, ALB, ECS service, alarms, log groups, and KMS consequences.
5. Apply only the reviewed destroy plan from the trusted WSL environment. Do
   not delete the remote-state bucket or its KMS key as part of the same step.
6. Remove the Cloudflare application CNAME only after the ALB is gone. Keep ACM
   validation records if the certificate/domain will be reused.
7. Verify that no NAT Gateway, ALB, ECS tasks, temporary RDS restore, or unused
   Elastic IP remains. Review Cost Explorer again after 24–48 hours.

Do not run teardown until the final snapshot requirement and retention period
are explicitly approved. Teardown is destructive even though Terraform can
recreate infrastructure; live database contents require the retained snapshot
or another validated export.

## Rebuild path

Recreate remote-state/OIDC prerequisites if needed, run the reviewed production
Terraform workflow with immutable app/importer digests, restore or recreate the
database, run migrations, import the exact versioned Olist bundle, deploy via
CD, and repeat public health plus row-count checks. DNS should be restored only
after the ALB and certificate are ready.
