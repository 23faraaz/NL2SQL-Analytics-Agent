# Production operations checklist

Use this checklist after material releases and on the stated cadence. Record
the date, operator, evidence link, and any follow-up issue for every exception.

## Weekly

- Check all `production-nl2sql-*` CloudWatch alarms are enabled and either `OK`
  or have a documented incident.
- Confirm the public HTTPS health endpoint returns `ok`.
- Review the latest main-branch CI run, Trivy reports, and open Dependabot PRs.
- Check actual and forecast AWS spend against the USD 20 warning threshold.

## Monthly

- Confirm the SNS operator subscription remains confirmed and send a controlled
  notification test if routing or recipients changed.
- Verify the latest automated RDS snapshot is `available`, encrypted, and within
  the approved 24-hour RPO. Confirm `LatestRestorableTime` advances.
- Review ACM certificate status, renewal eligibility, expiry, and DNS validation
  records. Investigate before expiry if managed renewal is not progressing.
- Review ECR/Trivy findings and Python, Docker, Terraform-provider, and GitHub
  Actions dependency updates. Apply supported security fixes through CI.
- Review CloudWatch logs, ALB access logs, dashboard signals, and backup/storage
  growth for unexpected gaps or sensitive data.

## Quarterly and after recovery-sensitive changes

- Repeat an RDS point-in-time restore and validate expected row counts.
- Repeat the deliberately unhealthy ECS deployment and rollback exercise.
- Review IAM/OIDC trust, `iam:PassRole` scope, secrets rotation, RPO/RTO, NAT
  design, availability target, and the cost/teardown decision.

## Audit — 2026-10-13

- All nine CloudWatch alarms were enabled and `OK`.
- The USD 20 budget had the confirmed operator recipient; actual spend was USD
  0.00 and forecast spend was USD 14.971, below the USD 16 warning point.
- RDS was `available`, encrypted, deletion-protected, and had a current encrypted
  automated snapshot plus point-in-time recovery. Backup retention was one day,
  matching the current account constraint and the approved 24-hour RPO.
- ACM was `ISSUED` for `faraazmo.co.uk`, eligible for managed renewal, in use,
  and valid until 2027-03-19.
- The latest main CI run passed its tests, Terraform scan, and Trivy gates.
- Dependabot alerts were disabled at audit time; weekly pip, Docker, and GitHub
  Actions update configuration was added. Repository vulnerability alerts must
  remain enabled for security-advisory monitoring.
