output "role_arn" {
  description = "ARN assumed by trusted CI jobs to publish to ECR"
  value       = aws_iam_role.ci_publisher.arn
}
